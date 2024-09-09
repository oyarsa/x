// Count the most common words in a markdown file.
// Excludes headings, code blocks and indented blocks.
package main

import (
	"flag"
	"fmt"
	"os"
	"regexp"
	"slices"
	"sort"
	"strings"
)

// cleanMarkdown removes headings, code blocks, and indented blocks from markdown content
func cleanMarkdown(content string) string {
	// Remove headings (lines starting with #)
	content = regexp.MustCompile(`(?m)^#.*$`).ReplaceAllString(content, "")
	// Remove fenced code blocks (content between ``` markers)
	content = regexp.MustCompile("(?s)```.*?```").ReplaceAllString(content, "")

	// Remove indented code blocks (4 spaces or 1 tab at start of line)
	var cleanedLines []string
	inIndentedBlock := false
	for _, line := range strings.Split(content, "\n") {
		if strings.HasPrefix(line, "    ") || strings.HasPrefix(line, "\t") {
			inIndentedBlock = true
			continue
		}

		if !inIndentedBlock {
			cleanedLines = append(cleanedLines, line)
		}
		inIndentedBlock = false
	}
	content = strings.Join(cleanedLines, "\n")

	return content
}

// isStopWord checks if a word is a common English stop word
func isStopWord(word string) bool {
	return slices.Contains([]string{
		"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
		"in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "were", "will",
		"with",
	}, word)
}

// In this listed checks if a word is blacklisted
// In this context, we are blacklisting programming languages
func isBlacklisted(word string) bool {
	return slices.Contains([]string{
		"python", "go", "rust", "clojure", "fish", "sh",
	}, word)
}

func main() {
	numWords := flag.Int("n", 20, "Number of top words to display")
	minLength := flag.Int("min-length", 6, "Minimum word length to include in the count")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [OPTIONS] FILE_PATH\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "Options:\n")
		flag.PrintDefaults()
	}

	flag.Parse()

	if flag.NArg() < 1 {
		fmt.Println("Error: File path is required")
		flag.Usage()
		os.Exit(1)
	}

	filePath := flag.Arg(0)
	content, err := os.ReadFile(filePath)
	if err != nil {
		fmt.Printf("Error reading file: %v\n", err)
		os.Exit(1)
	}

	cleanedContent := cleanMarkdown(strings.ToLower(string(content)))
	// Remove non-alphabetic characters
	cleanedContent = regexp.MustCompile(`[^a-z\s]`).ReplaceAllString(cleanedContent, "")

	words := strings.Fields(cleanedContent)

	// Count words
	wordCount := make(map[string]int)
	for _, word := range words {
		if len(word) >= *minLength && !isStopWord(word) && !isBlacklisted(word) {
			wordCount[word]++
		}
	}

	// Sort words by count
	type wordFreq struct {
		word  string
		count int
	}
	var wf []wordFreq
	for word, count := range wordCount {
		wf = append(wf, wordFreq{word, count})
	}
	sort.Slice(wf, func(i, j int) bool {
		return wf[i].count > wf[j].count
	})

	for i := 0; i < *numWords && i < len(wf); i++ {
		fmt.Printf("%5d %s\n", wf[i].count, wf[i].word)
	}
}
