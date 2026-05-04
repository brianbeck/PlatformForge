// Trivy Admission Provider — Gatekeeper External Data Provider
// Queries Trivy Operator VulnerabilityReport CRDs and returns
// whether container images have CRITICAL CVEs.
//
// Implements the Gatekeeper External Data Provider API:
// https://open-policy-agent.github.io/gatekeeper/website/docs/externaldata
package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/rest"
)

// Gatekeeper External Data API types
type ProviderRequest struct {
	APIVersion string        `json:"apiVersion"`
	Kind       string        `json:"kind"`
	Request    RequestDetail `json:"request"`
}

type RequestDetail struct {
	Keys []string `json:"keys"`
}

type ProviderResponse struct {
	APIVersion string         `json:"apiVersion"`
	Kind       string         `json:"kind"`
	Response   ResponseDetail `json:"response"`
}

type ResponseDetail struct {
	Idempotent bool       `json:"idempotent"`
	Items      []ItemResult `json:"items"`
}

type ItemResult struct {
	Key   string      `json:"key"`
	Value interface{} `json:"value"`
	Error string      `json:"error"`
}

type CVEResult struct {
	HasCritical   bool     `json:"hasCritical"`
	CriticalCount int      `json:"criticalCount"`
	CVEs          []string `json:"cves"`
}

var (
	vulnerabilityReportGVR = schema.GroupVersionResource{
		Group:    "aquasecurity.github.io",
		Version:  "v1alpha1",
		Resource: "vulnerabilityreports",
	}
	dynamicClient dynamic.Interface
)

func main() {
	// In-cluster Kubernetes client
	config, err := rest.InClusterConfig()
	if err != nil {
		log.Fatalf("Failed to get in-cluster config: %v", err)
	}

	dynamicClient, err = dynamic.NewForConfig(config)
	if err != nil {
		log.Fatalf("Failed to create dynamic client: %v", err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/validate", handleValidate)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, "ok")
	})

	tlsCert := os.Getenv("TLS_CERT_FILE")
	tlsKey := os.Getenv("TLS_KEY_FILE")

	if tlsCert == "" {
		tlsCert = "/certs/tls.crt"
	}
	if tlsKey == "" {
		tlsKey = "/certs/tls.key"
	}

	server := &http.Server{
		Addr:    ":8443",
		Handler: mux,
		TLSConfig: &tls.Config{
			MinVersion: tls.VersionTLS13,
		},
	}

	log.Println("Starting trivy-admission-provider on :8443")
	if err := server.ListenAndServeTLS(tlsCert, tlsKey); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

func handleValidate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req ProviderRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("failed to decode request: %v", err), http.StatusBadRequest)
		return
	}

	items := make([]ItemResult, 0, len(req.Request.Keys))
	for _, imageRef := range req.Request.Keys {
		result, err := checkImage(r.Context(), imageRef)
		if err != nil {
			items = append(items, ItemResult{
				Key:   imageRef,
				Error: err.Error(),
			})
			continue
		}
		items = append(items, ItemResult{
			Key:   imageRef,
			Value: result,
		})
	}

	resp := ProviderResponse{
		APIVersion: "externaldata.gatekeeper.sh/v1beta1",
		Kind:       "ProviderResponse",
		Response: ResponseDetail{
			Idempotent: true,
			Items:      items,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func checkImage(ctx context.Context, imageRef string) (*CVEResult, error) {
	// Search all VulnerabilityReports across all namespaces
	reports, err := dynamicClient.Resource(vulnerabilityReportGVR).
		Namespace("").
		List(ctx, metav1.ListOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to list VulnerabilityReports: %v", err)
	}

	// Normalize the image reference for comparison
	normalizedRef := normalizeImage(imageRef)

	result := &CVEResult{
		HasCritical:   false,
		CriticalCount: 0,
		CVEs:          []string{},
	}

	for _, report := range reports.Items {
		reportImage := getReportImage(&report)
		if normalizeImage(reportImage) != normalizedRef {
			continue
		}

		// Found a matching report — extract critical CVEs
		criticals := extractCriticalCVEs(&report)
		result.CriticalCount += len(criticals)
		result.CVEs = append(result.CVEs, criticals...)
	}

	if result.CriticalCount > 0 {
		result.HasCritical = true
	}

	// Cap CVE list to avoid huge responses
	if len(result.CVEs) > 10 {
		result.CVEs = append(result.CVEs[:10], "...")
	}

	return result, nil
}

func getReportImage(report *unstructured.Unstructured) string {
	artifact, found, _ := unstructured.NestedMap(report.Object, "report", "artifact")
	if !found {
		return ""
	}
	repo, _ := artifact["repository"].(string)
	tag, _ := artifact["tag"].(string)
	digest, _ := artifact["digest"].(string)

	if digest != "" {
		return fmt.Sprintf("%s@%s", repo, digest)
	}
	if tag != "" {
		return fmt.Sprintf("%s:%s", repo, tag)
	}
	return repo
}

func extractCriticalCVEs(report *unstructured.Unstructured) []string {
	vulns, found, _ := unstructured.NestedSlice(report.Object, "report", "vulnerabilities")
	if !found {
		return nil
	}

	var criticals []string
	for _, v := range vulns {
		vuln, ok := v.(map[string]interface{})
		if !ok {
			continue
		}
		severity, _ := vuln["severity"].(string)
		if strings.EqualFold(severity, "CRITICAL") {
			vulnID, _ := vuln["vulnerabilityID"].(string)
			if vulnID != "" {
				criticals = append(criticals, vulnID)
			}
		}
	}
	return criticals
}

func normalizeImage(ref string) string {
	// Strip docker.io/ prefix and :latest suffix for comparison
	ref = strings.TrimPrefix(ref, "docker.io/")
	ref = strings.TrimPrefix(ref, "library/")

	// If no tag or digest, assume :latest
	if !strings.Contains(ref, ":") && !strings.Contains(ref, "@") {
		ref = ref + ":latest"
	}
	return ref
}
