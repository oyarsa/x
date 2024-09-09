//go:build countsymbols

// Count ASCII symbols in code files in a given directory.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"sync"
)

func isCodeFile(filename string) bool {
	codeExtensions := map[string]bool{
		".py": true, ".fish": true,
		".go": true, ".js": true, ".java": true,
		".cpp": true, ".c": true, ".h": true, ".cs": true,
		".rb": true, ".php": true, ".rs": true, ".ts": true,
	}
	ext := filepath.Ext(filename)
	_, exists := codeExtensions[ext]
	return exists
}

func isASCIISymbol(r rune) bool {
	return r > 32 && r < 127 &&
		!((r >= '0' && r <= '9') || (r >= 'A' && r <= 'Z') || (r >= 'a' && r <= 'z'))
}

func countSymbols(filePath string) map[rune]int {
	symbolCount := make(map[rune]int)
	content, err := os.ReadFile(filePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading file %s: %v\n", filePath, err)
		return symbolCount
	}

	for _, char := range string(content) {
		if isASCIISymbol(char) {
			symbolCount[char]++
		}
	}
	return symbolCount
}

func worker(jobs <-chan string, results chan<- map[rune]int, wg *sync.WaitGroup) {
	defer wg.Done()
	for filePath := range jobs {
		results <- countSymbols(filePath)
	}
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Usage: go run script.go <path1> [path2] [path3] ...")
		os.Exit(1)
	}

	paths := os.Args[1:]

	jobs := make(chan string, 100)
	results := make(chan map[rune]int, 100)

	var wg sync.WaitGroup
	numWorkers := runtime.NumCPU()
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go worker(jobs, results, &wg)
	}

	go func() {
		for _, path := range paths {
			err := filepath.Walk(path, func(path string, info os.FileInfo, err error) error {
				if err != nil {
					return err
				}
				if !info.IsDir() && isCodeFile(path) {
					jobs <- path
				}
				return nil
			})
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error walking path %s: %v\n", path, err)
			}
		}
		close(jobs)
	}()

	go func() {
		wg.Wait()
		close(results)
	}()

	totalSymbolCount := make(map[rune]int)
	for result := range results {
		for symbol, count := range result {
			totalSymbolCount[symbol] += count
		}
	}

	type symbolCount struct {
		symbol rune
		count  int
	}
	symbolCounts := make([]symbolCount, 0, len(totalSymbolCount))

	for symbol, count := range totalSymbolCount {
		symbolCounts = append(symbolCounts, symbolCount{symbol: symbol, count: count})
	}

	sort.Slice(symbolCounts, func(i, j int) bool {
		return symbolCounts[i].count > symbolCounts[j].count
	})

	for _, sc := range symbolCounts {
		fmt.Printf("%c %d\n", sc.symbol, sc.count)
	}
}
