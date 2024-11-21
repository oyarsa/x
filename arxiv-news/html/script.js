// Constants
const BLOCKLIST_WORDS = [
  "audio",
  "bio",
  "biology",
  "chemical",
  "chemistry",
  "drug",
  "memo",
  "modal",
  "molecule",
  "mri",
  "protein",
  "speech",
  "video",
  "vision",
  "visual",
  "x-ray",
  "basque",
  "chinese",
  "french",
  "greek",
  "hindi",
  "indian",
  "japanese",
  "portuguese",
  "romanian",
  "spanish",
];

const HIGHLIGHT_TOPICS = ["know", "graph", "sci"];

// Functions
function extractPapers(text) {
  const paperParts = text.split("\n\\\\");
  const papers = [];

  for (const part of paperParts) {
    const arxivMatch = part.match(/arXiv:(\d+\.\d+)/);
    if (!arxivMatch) continue;

    const arxivId = arxivMatch[1];
    const titleMatch = part.match(/Title: (.*?)(?:\nAuthors:|$)/s);

    if (titleMatch) {
      const title = titleMatch[1].trim().replace(/\s+/g, " ");
      const link = `https://arxiv.org/abs/${arxivId}`;
      papers.push({ title, link });
    }
  }

  return papers;
}

function isValidTitle(title) {
  return !BLOCKLIST_WORDS.some((word) =>
    title.toLowerCase().includes(word.toLowerCase()),
  );
}

function hasHighlight(title) {
  return HIGHLIGHT_TOPICS.some((topic) =>
    title.toLowerCase().includes(topic.toLowerCase()),
  );
}

function createPaperElement(paper, index, highlighted) {
  return `
        <div class="flex gap-4 p-4 mb-3 rounded-md border
                    ${highlighted ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white"}">
            <div class="flex-shrink-0 w-6 text-center">${index + 1}.</div>
            <div class="flex-grow">
                <a href="${paper.link}" class="text-blue-500 hover:underline font-medium"
                   target="_blank" rel="noopener noreferrer">
                    ${paper.title}
                </a>
            </div>
        </div>
    `;
}

function displayPapers(papers) {
  const validPapers = papers.filter((p) => isValidTitle(p.title));
  const highlightedPapers = validPapers.filter((p) => hasHighlight(p.title));
  const otherPapers = validPapers.filter((p) => !hasHighlight(p.title));

  // Update stats
  document.getElementById("stats").textContent =
    `Total papers: ${papers.length} | Valid papers: ${validPapers.length}` +
    ` | Highlighted: ${highlightedPapers.length}`;

  // Display highlighted papers
  const highlightedContainer = document.getElementById("highlighted-papers");
  highlightedContainer.innerHTML = `<h2>Highlighted Papers</h2>${highlightedPapers.map((p, i) => createPaperElement(p, i, true)).join("")}`;

  // Display other papers
  const otherContainer = document.getElementById("other-papers");
  otherContainer.innerHTML = `<h2>Other Papers</h2>${otherPapers.map((p, i) => createPaperElement(p, i, false)).join("")}`;

  document.getElementById("results").style.display = "block";
}

async function processURL(url) {
  try {
    const response = await fetch(url);
    if (!response.ok)
      throw new Error(
        `Failed to fetch URL: ${response.status} ${response.statusText}`,
      );
    const text = await response.text();
    return extractPapers(text);
  } catch (error) {
    if (error.name === "TypeError" && error.message.includes("CORS")) {
      throw new Error(
        "Cannot access this URL directly due to browser security restrictions (CORS)." +
          " Please copy and paste the content instead.",
      );
    }
    throw new Error(`Failed to fetch URL: ${error.message}`);
  }
}

// Event Listeners
document.addEventListener("DOMContentLoaded", () => {
  const urlInput = document.getElementById("url");
  urlInput.focus();

  // Add Enter key event listener
  urlInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      document.getElementById("process-url").click();
    }
  });

  // Set initial active tab styling
  const urlTab = document.querySelector('[data-tab="url"]');
  urlTab.classList.add("bg-blue-500", "text-white");
  urlTab.classList.remove("text-blue-500");

  // Tab switching
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => {
        t.classList.remove("active", "bg-blue-500", "text-white");
        t.classList.add("text-blue-500");
      });
      document
        .querySelectorAll(".tab-content")
        .forEach((c) => c.classList.add("hidden"));

      tab.classList.add("active", "bg-blue-500", "text-white");
      tab.classList.remove("text-blue-500");
      document
        .getElementById(`${tab.dataset.tab}-tab`)
        .classList.remove("hidden");
    });
  });

  // Process content button
  document.getElementById("process-content").addEventListener("click", () => {
    const content = document.getElementById("content").value;
    if (!content) return;

    try {
      const papers = extractPapers(content);
      displayPapers(papers);
      document.getElementById("error").style.display = "none";
    } catch {
      document.getElementById("error").textContent =
        "Failed to process content";
      document.getElementById("error").style.display = "block";
    }
  });

  // Process URL button
  document.getElementById("process-url").addEventListener("click", async () => {
    const url = document.getElementById("url").value;
    if (!url) return;

    const loading = document.getElementById("loading");
    const error = document.getElementById("error");

    try {
      loading.classList.add("active");
      error.style.display = "none";

      const papers = await processURL(url);
      displayPapers(papers);
    } catch (err) {
      error.textContent = err.message;
      error.style.display = "block";
    } finally {
      loading.classList.remove("active");
    }
  });
});
