package api

import "strings"

func NormalizePath(path string) string {
	return strings.TrimSuffix(path, "/")
}
