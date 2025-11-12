# Git Load Tester (Python)

A Git protocol load testing tool that supports both HTTPS and SSH transports.

## Features

- ✅ **HTTPS Transport**: Clone from any git server over HTTPS
- ✅ **SSH Transport**: Clone from any git server over SSH
- ✅ **Concurrent Operations**: Run multiple clones simultaneously
- ✅ **Non-materializing**: Streams pack data without writing to disk
- ✅ **Metrics**: Track throughput, duration, and success/failure rates

## Installation

```bash
cd load-tester-python
pip install -r requirements.txt
```

## Usage

### HTTPS Clone

```bash
python -m git_load_tester.main https://github.com/rust-lang/rustlings.git --concurrency 5 --count 10
```

### SSH Clone

```bash
python -m git_load_tester.main git@github.com:rust-lang/rustlings.git --concurrency 5 --count 10
```

### Local SSH Clone

```bash
python -m git_load_tester.main kdspaul@localhost:/Users/kdspaul/workspace/linux --concurrency 2 --count 5
```

### Options

- `-c, --concurrency N`: Number of concurrent clone operations (default: 10)
- `-n, --count N`: Total number of clone operations (default: 100)
- `-v, --verbose`: Verbose output (show each clone completion)

## How It Works

1. **Ref Discovery**: Fetches available refs from the remote repository
2. **Pack Negotiation**: Sends `want` requests for the default ref (HEAD/main/master)
3. **Pack Reception**: Streams pack data without materializing to disk
4. **Metrics**: Tracks bytes received, duration, and throughput

## SSH Authentication

For SSH transport, the tool uses your SSH agent or SSH keys in `~/.ssh/`:
- `id_rsa`
- `id_ed25519`
- `id_ecdsa`

Make sure your SSH keys are loaded in ssh-agent or have no passphrase for load testing.

## Example Output

```
Git Load Tester starting...
URL: https://github.com/rust-lang/rustlings.git
Concurrency: 2
Count: 2

Detected protocol: HTTPS

Clone #1 completed: 4,351,033 bytes
Clone #2 completed: 4,351,078 bytes

====== Summary ======
Total clones: 2
Successful: 2
Failed: 0
Total bytes: 8,702,111 (8.30 MB)
Duration: 1.23s
Throughput: 6.75 MB/s
Avg time per clone: 0.62s
```

## Architecture

- `protocol.py`: Git pkt-line protocol parser and ref advertisement handling
- `https_transport.py`: HTTPS transport implementation
- `ssh_transport.py`: SSH transport implementation using paramiko
- `main.py`: CLI interface and concurrent clone orchestration
