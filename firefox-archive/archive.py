"""Domain-aware concurrent page archival using monolith."""

import argparse
import asyncio
import contextlib
import hashlib
import logging
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from tqdm import tqdm

logger = logging.getLogger("archive")


@dataclass(frozen=True, kw_only=True)
class ArchiveConfig:
    output_dir: Path = Path("archived")
    global_concurrency: int = 20
    per_domain_concurrency: int = 2
    timeout: int = 30
    max_retries: int = 2
    retry_backoff: float = 5.0
    monolith_extra_args: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class ArchiveResult:
    url: str
    output: Path | None
    success: bool
    error: str | None = None


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _output_path(url: str, output_dir: Path) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:12]
    parsed = urlparse(url)

    slug = parsed.path.strip("/").replace("/", "_")[:80] or "index"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in slug)

    return output_dir / parsed.netloc / f"{safe}_{h}.html"


async def _archive_one(
    url: str,
    config: ArchiveConfig,
    global_sem: asyncio.Semaphore,
    domain_sems: dict[str, asyncio.Semaphore],
) -> ArchiveResult:
    domain = _domain(url)
    domain_sem = domain_sems[domain]
    output = _output_path(url, config.output_dir)
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "monolith",
        url,
        "-o",
        str(output),
        "-e",  # ignore network errors
        "-q",  # quiet
        "-t",
        str(config.timeout),
        *config.monolith_extra_args,
    ]

    for attempt in range(1 + config.max_retries):
        if attempt > 0:
            delay = config.retry_backoff * (2 ** (attempt - 1))
            await asyncio.sleep(delay)

        async with global_sem, domain_sem:
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=config.timeout + 10,
                )

                if proc.returncode == 0 and output.exists():
                    logger.debug("OK %s", url)
                    return ArchiveResult(url=url, output=output, success=True)
                else:
                    err = stderr.decode(errors="replace").strip()
                    logger.warning("FAIL %s: %s", url, err or f"exit {proc.returncode}")
                    return ArchiveResult(
                        url=url, output=None, success=False, error=err
                    )

            except TimeoutError:
                logger.debug(
                    "TIMEOUT %s (attempt %d/%d)",
                    url,
                    attempt + 1,
                    1 + config.max_retries,
                )
                continue
            except Exception as e:
                logger.warning("ERROR %s: %s", url, e)
                return ArchiveResult(
                    url=url, output=None, success=False, error=str(e)
                )
            finally:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    with contextlib.suppress(BaseException):
                        await proc.wait()

    return ArchiveResult(url=url, output=None, success=False, error="timeout")


async def archive_urls(urls: list[str], config: ArchiveConfig) -> list[ArchiveResult]:
    config.output_dir.mkdir(parents=True, exist_ok=True)

    global_sem = asyncio.Semaphore(config.global_concurrency)
    domain_sems: dict[str, asyncio.Semaphore] = defaultdict(
        lambda: asyncio.Semaphore(config.per_domain_concurrency)
    )

    # Log domain distribution
    domain_counts: dict[str, int] = defaultdict(int)
    for url in urls:
        domain_counts[_domain(url)] += 1
    top = sorted(domain_counts.items(), key=lambda x: -x[1])[:10]

    logger.info(
        "%d URLs across %d domains. Top: %s",
        len(urls),
        len(domain_counts),
        ", ".join(f"{d}({n})" for d, n in top),
    )

    tasks = [_archive_one(url, config, global_sem, domain_sems) for url in urls]
    results: list[ArchiveResult] = []
    succeeded = 0
    failed = 0
    timed_out = 0

    with tqdm(total=len(tasks), unit="pg", dynamic_ncols=True) as bar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            if result.success:
                succeeded += 1
            elif result.error == "timeout":
                timed_out += 1
            else:
                failed += 1

            bar.set_description(
                f"ok={succeeded} fail={failed} timeout={timed_out}", refresh=False
            )
            bar.update()

    logger.info(
        "Done: %d/%d succeeded, %d timed out", succeeded, len(results), timed_out
    )
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    parser = argparse.ArgumentParser(description="Archive web pages using monolith")
    parser.add_argument("url_file", type=Path, help="NUL-delimited file of URLs")
    parser.add_argument(
        "-n", "--limit", type=int, default=None, help="Sample N URLs (seed=0)"
    )
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("archived"))
    parser.add_argument("-j", "--jobs", type=int, default=20, help="Global concurrency")
    parser.add_argument(
        "-d", "--domain-jobs", type=int, default=2, help="Per-domain concurrency"
    )
    parser.add_argument("-t", "--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2, help="Max retries for timeouts")
    parser.add_argument(
        "--retry-backoff", type=float, default=5.0, help="Initial backoff in seconds"
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    with open(args.url_file) as f:
        urls = [line for line in f if line.strip()]

    if args.limit is not None and args.limit < len(urls):
        urls = rng.sample(urls, args.limit)
        logger.info("Sampled %d URLs", len(urls))

    config = ArchiveConfig(
        output_dir=args.output_dir,
        global_concurrency=args.jobs,
        per_domain_concurrency=args.domain_jobs,
        timeout=args.timeout,
        max_retries=args.retries,
        retry_backoff=args.retry_backoff,
    )

    results = asyncio.run(archive_urls(urls, config))

    if failed := [r for r in results if not r.success]:
        print(f"\n{len(failed)} failures:")
        for r in failed:
            print(f"  {r.url}: {r.error}")
