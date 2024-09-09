# arxiv-news

Extract titles and links from arXiv's daily email and present them in a more readable
Markdown format.

## Usage

```sh
$ python titles.py <in >out
```

Input comes from stdin and outputs Markdown to stdout.

## Script

You can also use the `titles.fish`:

```sh
$ ./titles.fish $URL
```

Where `$URL` is the link to the raw email. In Fastmail, this can be found by clicking
on Actions > Show Raw Message. Copy the URL and paste it in the command above.

This requires `curl` and [`glow`](https://github.com/charmbracelet/glow).
