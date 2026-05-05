from __future__ import annotations

import argparse
import os

from oasis.aoasis.model_resolver import default_openrouter_model_resolver
from oasis.aoasis.worker import (AOASIS_WORKER_RUNTIME_MODES,
                                 AOasisWorkerService,
                                 make_aoasis_worker_server)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Atherum-compatible AOaSIS worker service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--data-dir", default=".aoasis-worker")
    parser.add_argument(
        "--runtime",
        choices=AOASIS_WORKER_RUNTIME_MODES,
        default=os.environ.get("AOASIS_WORKER_RUNTIME", "deterministic"),
        help=(
            "Worker runtime: deterministic is fast/no-network; oasis-manual "
            "runs the real OASIS environment with manual actions; oasis-llm "
            "uses the default OpenRouter/OpenAI-compatible model resolver."
        ),
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Complete runs before returning from POST /api/v1/simulations.",
    )
    args = parser.parse_args()

    service = AOasisWorkerService(
        args.data_dir,
        run_in_background=not args.sync,
        runtime_mode=args.runtime,
        model_resolver=(
            default_openrouter_model_resolver()
            if args.runtime == "oasis-llm" else None
        ),
    )
    server = make_aoasis_worker_server((args.host, args.port), service)
    print(
        f"AOaSIS worker listening on http://{args.host}:{args.port} "
        f"({args.runtime})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
