package main

import (
	"testing"
)

func TestGetUrl(t *testing.T) {
	tests := []struct {
		paths    []string
		expected string
	}{
		{[]string{}, "https://1557.kyiv.ua/"},
		{[]string{"login"}, "https://1557.kyiv.ua/login"},
		{[]string{"login", "pass"}, "https://1557.kyiv.ua/login/pass"},
	}

	for _, test := range tests {
		actual := getUrl(test.paths...)
		if actual != test.expected {
			t.Errorf("getUrl(%v): expected %s, actual %s", test.paths, test.expected, actual)
		}
	}
}
