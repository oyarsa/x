package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strconv"
)

const usage = `Usage: jhead [OPTIONS] [PATH] [COUNT]

Like 'head', but for JSON files with arrays.
Example:

    $ jhead file.json     # first 10 items of the file
    $ jhead file.json 5   # first 5 items of the file
    $ echo ... | jhead    # first 10 items from stdin
    $ echo ... | jhead 5  # first 5 items from stdin

Arguments:
    PATH    Path to JSON file, or "-" for stdin [default: -]
    COUNT   Number of items to show [default: 5]

Options:
    -h, --help    Show this message and exit`

func main() {
	help := flag.Bool("help", false, "display help")
	flag.BoolVar(help, "h", false, "display help")
	flag.Usage = func() { fmt.Fprintln(os.Stderr, usage) }
	flag.Parse()

	if *help {
		flag.Usage()
		os.Exit(0)
	}

	var count int = 5
	var filename string = "-"
	args := flag.Args()

	if len(args) > 0 {
		if n, err := strconv.Atoi(args[0]); err == nil {
			count = n
		} else {
			filename = args[0]
			if len(args) > 1 {
				if n, err := strconv.Atoi(args[1]); err == nil {
					count = n
				}
			}
		}
	}

	var r io.Reader = os.Stdin
	if filename != "-" {
		f, err := os.Open(filename)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error opening file: %v\n", err)
			os.Exit(1)
		}
		defer f.Close()
		r = f
	}

	dec := json.NewDecoder(r)

	t, err := dec.Token()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading JSON: %v\n", err)
		os.Exit(1)
	}
	if t != json.Delim('[') {
		fmt.Fprintf(os.Stderr, "Expected array, got %v\n", t)
		os.Exit(1)
	}

	items := make([]json.RawMessage, 0, count)
	for i := 0; i < count && dec.More(); i++ {
		var raw json.RawMessage
		if err := dec.Decode(&raw); err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding item %d: %v\n", i, err)
			os.Exit(1)
		}
		items = append(items, raw)
	}

	if len(items) == 0 {
		fmt.Print("[]\n")
		return
	}

	fmt.Print("[\n")
	for i, item := range items {
		indented, err := json.MarshalIndent(json.RawMessage(item), "    ", "    ")
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error formatting item %d: %v\n", i, err)
			os.Exit(1)
		}
		fmt.Printf("    %s", indented)
		if i < len(items)-1 {
			fmt.Print(",")
		}
		fmt.Print("\n")
	}
	fmt.Print("]\n")
}
