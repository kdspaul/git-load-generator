"""Main entry point for git load tester."""

import argparse
import time
import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .https_transport import HttpsTransport
from .ssh_transport import SshTransport


def is_ssh_url(url: str) -> bool:
    """Check if URL is SSH format."""
    return url.startswith('ssh://') or ('@' in url and ':' in url and '://' not in url)


# Global progress tracking
progress_lock = threading.Lock()
progress_data = {}  # clone_id -> (bytes_received, status)
progress_enabled = False
progress_stop = False


def update_progress_display():
    """Update the progress display in place."""
    global progress_stop

    while not progress_stop:
        with progress_lock:
            if progress_data:
                # Move cursor up and clear lines
                output = []
                for clone_id in sorted(progress_data.keys()):
                    bytes_received, status = progress_data[clone_id]
                    mb = bytes_received / 1_048_576
                    output.append(f"Thread #{clone_id} - {mb:>8.2f} MiB [{status}]")

                # Clear lines and print
                sys.stdout.write('\r' + '\033[K')  # Clear current line
                for i, line in enumerate(output):
                    if i > 0:
                        sys.stdout.write('\n')
                    sys.stdout.write(line)

                # Move cursor back up
                if len(output) > 1:
                    sys.stdout.write(f'\033[{len(output)-1}A')

                sys.stdout.flush()

        time.sleep(0.5)


def perform_clone(clone_id: int, url: str, is_ssh: bool) -> tuple:
    """Perform a single clone operation with progress tracking.

    Args:
        clone_id: Clone operation ID
        url: Repository URL
        is_ssh: Whether to use SSH transport

    Returns:
        Tuple of (clone_id, bytes_received, error)
    """
    global progress_enabled

    try:
        # Initialize progress
        if progress_enabled:
            with progress_lock:
                progress_data[clone_id] = (0, "starting")

        if is_ssh:
            from .ssh_transport_progress import SshTransportWithProgress

            def progress_callback(bytes_received):
                if progress_enabled:
                    with progress_lock:
                        progress_data[clone_id] = (bytes_received, "downloading")

            transport = SshTransportWithProgress(url, progress_callback)
        else:
            from .https_transport_progress import HttpsTransportWithProgress

            def progress_callback(bytes_received):
                if progress_enabled:
                    with progress_lock:
                        progress_data[clone_id] = (bytes_received, "downloading")

            transport = HttpsTransportWithProgress(url, progress_callback)

        bytes_received = transport.clone()

        if progress_enabled:
            with progress_lock:
                progress_data[clone_id] = (bytes_received, "complete")

        return (clone_id, bytes_received, None)
    except Exception as e:
        if progress_enabled:
            with progress_lock:
                progress_data[clone_id] = (0, f"failed: {str(e)[:20]}")
        return (clone_id, 0, str(e))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Git Load Tester - Load test git servers over HTTPS and SSH'
    )
    parser.add_argument('url', help='Git repository URL')
    parser.add_argument(
        '-c', '--concurrency',
        type=int,
        default=10,
        help='Number of concurrent clone operations (default: 10)'
    )
    parser.add_argument(
        '-n', '--count',
        type=int,
        default=100,
        help='Total number of clone operations (default: 100)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--progress',
        action='store_true',
        help='Show live progress display'
    )

    args = parser.parse_args()

    print(f"Git Load Tester starting...")
    print(f"URL: {args.url}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Count: {args.count}")
    print()

    is_ssh = is_ssh_url(args.url)
    protocol = "SSH" if is_ssh else "HTTPS"
    print(f"Detected protocol: {protocol}")
    print()

    start_time = time.time()
    total_bytes = 0
    successful = 0
    failed = 0

    # Enable progress display if requested
    global progress_enabled, progress_stop
    progress_enabled = args.progress
    progress_thread = None

    if progress_enabled:
        progress_stop = False
        progress_thread = threading.Thread(target=update_progress_display, daemon=True)
        progress_thread.start()
        # Give progress thread time to start
        time.sleep(0.1)

    executor = ThreadPoolExecutor(max_workers=args.concurrency)
    interrupted = False
    try:
        # Submit all clone tasks
        futures = []
        for i in range(args.count):
            future = executor.submit(perform_clone, i + 1, args.url, is_ssh)
            futures.append(future)

        # Process results as they complete
        for future in as_completed(futures):
            clone_id, bytes_received, error = future.result()

            if error:
                print(f"Clone #{clone_id} failed: {error}")
                failed += 1
            else:
                if args.verbose:
                    print(f"Clone #{clone_id} completed: {bytes_received:,} bytes")
                total_bytes += bytes_received
                successful += 1

    except KeyboardInterrupt:
        interrupted = True

        # Stop progress display
        if progress_enabled and progress_thread:
            progress_stop = True
            progress_thread.join(timeout=0.5)
            # Clear progress lines
            with progress_lock:
                if progress_data:
                    num_lines = len(progress_data)
                    sys.stdout.write('\n' * num_lines)
                    sys.stdout.flush()

        print("\n\nInterrupted by user. Exiting...")
        sys.stdout.flush()

        # Force immediate exit without cleanup to avoid hanging on I/O threads
        os._exit(130)  # Standard exit code for Ctrl-C
    finally:
        # Only wait for executor cleanup if not interrupted
        if not interrupted:
            executor.shutdown(wait=True)

    # Stop progress display
    if progress_enabled and progress_thread:
        progress_stop = True
        progress_thread.join(timeout=1)
        # Clear progress lines
        with progress_lock:
            if progress_data:
                num_lines = len(progress_data)
                sys.stdout.write('\n' * num_lines)
                sys.stdout.flush()

    duration = time.time() - start_time
    total_mb = total_bytes / 1_048_576
    mbps = total_mb / duration if duration > 0 else 0

    print()
    print("====== Summary ======")
    print(f"Total clones: {args.count}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total bytes: {total_bytes:,} ({total_mb:.2f} MB)")
    print(f"Duration: {duration:.2f}s")
    print(f"Throughput: {mbps:.2f} MB/s")
    print(f"Avg time per clone: {duration / args.count:.2f}s")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
