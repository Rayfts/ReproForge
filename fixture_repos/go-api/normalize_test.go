package api

import "testing"

func TestRootPathStaysRoot(t *testing.T) {
	if got := NormalizePath("/"); got != "/" {
		t.Fatalf("NormalizePath(/) = %q; want /", got)
	}
}
