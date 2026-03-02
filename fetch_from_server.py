#!/usr/bin/env python3
"""Script to fetch files from remote server using SSH"""

import paramiko
import os
from pathlib import Path

# Server details
host = "195.88.87.86"
port = 22
username = "root"
password = "Savabubamala11"
remote_path = "/srv"
local_path = "d:/dule/citko/e-citko/ecitko"

# Create SSH client
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, port=port, username=username, password=password, timeout=10)
    print("✓ Connected!")
    
    # List files on remote server
    stdin, stdout, stderr = ssh.exec_command(f"find {remote_path} -type f \\( -name '*.py' -o -name '*.txt' -o -name '*.yml' -o -name '*.sql' -o -name '*.ini' -o -name '.*' \\) | sort")
    
    remote_files = [line.strip() for line in stdout.readlines() if line.strip()]
    print(f"\nFound {len(remote_files)} files on server:")
    print("-" * 80)
    for file in remote_files:
        print(file)
    
    # Get local files
    local_files = set()
    for root, dirs, files in os.walk(local_path):
        for file in files:
            full_path = os.path.relpath(os.path.join(root, file), local_path)
            local_files.add(full_path.replace("\\", "/"))
    
    print(f"\n{len(local_files)} files locally")
    
    # Compare
    print("\n" + "=" * 80)
    print("FILES ON SERVER BUT NOT LOCAL:")
    print("=" * 80)
    
    sftp = ssh.open_sftp()
    missing_files = []
    
    for remote_file in remote_files:
        # Convert remote path to relative
        rel_file = remote_file.replace(f"{remote_path}/", "").replace(f"{remote_path}", "")
        
        if rel_file and not rel_file.startswith("/"):
            if rel_file not in local_files:
                missing_files.append((remote_file, rel_file))
                print(f"  {rel_file}")
    
    if missing_files:
        print(f"\n{len(missing_files)} missing file(s) found!")
    else:
        print("All server files are already local!")
    
    # Optionally download missing files
    if missing_files:
        print("\n" + "=" * 80)
        response = input("Download missing files? (y/n): ").strip().lower()
        
        if response == 'y':
            for remote_file, rel_file in missing_files:
                try:
                    local_file = os.path.join(local_path, rel_file)
                    os.makedirs(os.path.dirname(local_file), exist_ok=True)
                    
                    sftp.get(remote_file, local_file)
                    print(f"✓ Downloaded: {rel_file}")
                except Exception as e:
                    print(f"✗ Error downloading {rel_file}: {e}")
    
    sftp.close()
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
    print("\nDone!")
