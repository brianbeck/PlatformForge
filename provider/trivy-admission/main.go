// Trivy Admission Provider — Gatekeeper External Data Provider
// Queries Trivy Operator VulnerabilityReport CRDs and returns
// whether container images have CRITICAL/HIGH CVEs.
//
// Uses an informer cache so /validate is an O(1) map lookup instead
// of a full LIST against the Kubernetes API on every admission request.
//
// Implements the Gatekeeper External Data Provider API:
// https://open-policy-agent.github.io/gatekeeper/website/docs/externaldata
package main

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/dynamic/dynamicinformer"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/cache"
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
	Idempotent bool         `json:"idempotent"`
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
	HasHigh       bool     `json:"hasHigh"`
	HighCount     int      `json:"highCount"`
	CVEs          []string `json:"cves"`
}

// reportSummary holds the pre-computed CVE counts for one VulnerabilityReport.
// Stored in the cache so /validate doesn't need to re-parse the report.
type reportSummary struct {
	criticals []string
	highs     []string
}

// ReportCache indexes VulnerabilityReport summaries by normalized image ref.
// Multiple reports can match the same image (different scan timestamps,
// different namespaces); we sum their CVE counts in lookup().
type ReportCache struct {
	mu sync.RWMutex
	// key: normalized image ref → key: report UID → summary
	byImage map[string]map[string]*reportSummary
}

func newReportCache() *ReportCache {
	return &ReportCache{
		byImage: make(map[string]map[string]*reportSummary),
	}
}

func (c *ReportCache) upsert(uid, image string, s *reportSummary) {
	if image == "" || uid == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	// Remove the report from its previous image bucket (image may have changed)
	for img, reports := range c.byImage {
		if _, ok := reports[uid]; ok && img != image {
			delete(reports, uid)
			if len(reports) == 0 {
				delete(c.byImage, img)
			}
		}
	}
	if _, ok := c.byImage[image]; !ok {
		c.byImage[image] = make(map[string]*reportSummary)
	}
	c.byImage[image][uid] = s
}

func (c *ReportCache) delete(uid string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for img, reports := range c.byImage {
		if _, ok := reports[uid]; ok {
			delete(reports, uid)
			if len(reports) == 0 {
				delete(c.byImage, img)
			}
		}
	}
}

func (c *ReportCache) lookup(image string) *CVEResult {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := &CVEResult{CVEs: []string{}}
	reports, ok := c.byImage[image]
	if !ok {
		return result
	}
	for _, s := range reports {
		result.CriticalCount += len(s.criticals)
		result.HighCount += len(s.highs)
		result.CVEs = append(result.CVEs, s.criticals...)
		result.CVEs = append(result.CVEs, s.highs...)
	}
	if result.CriticalCount > 0 {
		result.HasCritical = true
	}
	if result.HighCount > 0 {
		result.HasHigh = true
	}
	if len(result.CVEs) > 10 {
		result.CVEs = append(result.CVEs[:10], "...")
	}
	return result
}

var (
	vulnerabilityReportGVR = schema.GroupVersionResource{
		Group:    "aquasecurity.github.io",
		Version:  "v1alpha1",
		Resource: "vulnerabilityreports",
	}
	reportCache = newReportCache()
)

func main() {
	config, err := rest.InClusterConfig()
	if err != nil {
		log.Fatalf("Failed to get in-cluster config: %v", err)
	}

	dynamicClient, err := dynamic.NewForConfig(config)
	if err != nil {
		log.Fatalf("Failed to create dynamic client: %v", err)
	}

	stopCh := make(chan struct{})
	defer close(stopCh)

	startInformer(dynamicClient, stopCh)

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

// startInformer watches VulnerabilityReports cluster-wide and keeps
// reportCache up to date. Resync every 10m as a safety net against
// missed events.
func startInformer(client dynamic.Interface, stopCh <-chan struct{}) {
	factory := dynamicinformer.NewDynamicSharedInformerFactory(client, 10*time.Minute)
	informer := factory.ForResource(vulnerabilityReportGVR).Informer()

	informer.AddEventHandler(cache.ResourceEventHandlerFuncs{
		AddFunc:    func(obj interface{}) { onUpsert(obj) },
		UpdateFunc: func(_, obj interface{}) { onUpsert(obj) },
		DeleteFunc: onDelete,
	})

	go informer.Run(stopCh)

	log.Println("Waiting for VulnerabilityReport informer cache to sync...")
	if !cache.WaitForCacheSync(stopCh, informer.HasSynced) {
		log.Fatal("Failed to sync VulnerabilityReport informer cache")
	}
	log.Printf("Informer cache synced (%d images indexed)", reportCache.size())
}

func (c *ReportCache) size() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.byImage)
}

func onUpsert(obj interface{}) {
	report, ok := obj.(*unstructured.Unstructured)
	if !ok {
		return
	}
	image := normalizeImage(getReportImage(report))
	if image == "" {
		return
	}
	criticals, highs := extractCVEs(report)
	reportCache.upsert(string(report.GetUID()), image, &reportSummary{
		criticals: criticals,
		highs:     highs,
	})
}

func onDelete(obj interface{}) {
	// Handle DeletedFinalStateUnknown for completeness
	if tombstone, ok := obj.(cache.DeletedFinalStateUnknown); ok {
		obj = tombstone.Obj
	}
	report, ok := obj.(*unstructured.Unstructured)
	if !ok {
		return
	}
	reportCache.delete(string(report.GetUID()))
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
		result := reportCache.lookup(normalizeImage(imageRef))
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
	if err := json.NewEncoder(w).Encode(resp); err != nil {
		log.Printf("failed to encode response: %v", err)
	}
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

func extractCVEs(report *unstructured.Unstructured) (criticals []string, highs []string) {
	vulns, found, _ := unstructured.NestedSlice(report.Object, "report", "vulnerabilities")
	if !found {
		return nil, nil
	}

	for _, v := range vulns {
		vuln, ok := v.(map[string]interface{})
		if !ok {
			continue
		}
		severity, _ := vuln["severity"].(string)
		vulnID, _ := vuln["vulnerabilityID"].(string)
		if vulnID == "" {
			continue
		}
		switch {
		case strings.EqualFold(severity, "CRITICAL"):
			criticals = append(criticals, vulnID)
		case strings.EqualFold(severity, "HIGH"):
			highs = append(highs, vulnID)
		}
	}
	return criticals, highs
}

func normalizeImage(ref string) string {
	// Strip docker.io/ prefix for comparison consistency.
	ref = strings.TrimPrefix(ref, "docker.io/")
	ref = strings.TrimPrefix(ref, "library/")

	// If no tag or digest, assume :latest
	if !strings.Contains(ref, ":") && !strings.Contains(ref, "@") {
		ref = ref + ":latest"
	}
	return ref
}
