FROM golang:1.24-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -o trivy-admission-provider .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/trivy-admission-provider /trivy-admission-provider
USER nonroot:nonroot
ENTRYPOINT ["/trivy-admission-provider"]
