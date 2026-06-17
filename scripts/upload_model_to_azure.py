import os
import argparse
from azure.storage.fileshare import ShareClient, ShareFileClient, ShareDirectoryClient

def upload_with_progress(conn_str, share_name, local_path, remote_dir=""):
    if not os.path.exists(local_path):
        print(f"Error: Local file '{local_path}' does not exist.")
        return False
        
    filename = os.path.basename(local_path)
    file_size = os.path.getsize(local_path)
    
    # Ensure share exists
    share_client = ShareClient.from_connection_string(conn_str, share_name)
    try:
        share_client.create_share()
        print(f"Created file share '{share_name}'")
    except Exception:
        # Share already exists
        pass

    # Ensure remote directory exists if specified
    if remote_dir:
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, remote_dir)
        try:
            dir_client.create_directory()
            print(f"Created remote directory '{remote_dir}'")
        except Exception:
            pass
            
    remote_path = f"{remote_dir}/{filename}" if remote_dir else filename
    file_client = ShareFileClient.from_connection_string(
        conn_str=conn_str,
        share_name=share_name,
        file_path=remote_path
    )
    
    print(f"\nStarting upload of {local_path} ({file_size / (1024**3):.2f} GB)")
    print(f"Destination: Share '{share_name}', Path: '{remote_path}'")
    
    # Create the file with the expected size on Azure
    file_client.create_file(file_size)
    
    chunk_size = 4 * 1024 * 1024 # 4MB chunks (maximum allowed by Azure Files REST API)
    offset = 0
    import time
    
    with open(local_path, "rb") as f:
        while True:
            # Try to read the chunk with retries in case of transient I/O errors (e.g. external drive sleep)
            chunk = None
            for read_retry in range(5):
                try:
                    f.seek(offset)
                    chunk = f.read(chunk_size)
                    break
                except OSError as e:
                    if read_retry == 4:
                        raise e
                    print(f"\n[Warning] Local disk read error at offset {offset}: {e}. Retrying in 5 seconds...")
                    time.sleep(5)
            
            if not chunk:
                break
            
            # Upload this chunk with retries in case of transient network errors
            for upload_retry in range(5):
                try:
                    file_client.upload_range(chunk, offset, len(chunk))
                    break
                except Exception as e:
                    if upload_retry == 4:
                        raise e
                    print(f"\n[Warning] Upload error at offset {offset}: {e}. Retrying in 5 seconds...")
                    time.sleep(5)
            
            offset += len(chunk)
            
            percent = (offset / file_size) * 100
            print(f"Progress: {offset / (1024**2):.1f} MB / {file_size / (1024**2):.1f} MB ({percent:.1f}%)", end="\r", flush=True)
            
    print(f"\nUpload complete for {filename}!")
    return True

def main():
    parser = argparse.ArgumentParser(description="Upload Gemma GGUF model files to Azure Files")
    parser.add_argument("--conn-string", required=True, help="Azure Storage Connection String")
    parser.add_argument("--share-name", default="models", help="Azure Files Share Name (default: 'models')")
    parser.add_argument("--model-dir", default="google_gemma-4-E4B-it-GGUF", help="Directory containing the model GGUF files")
    
    args = parser.parse_args()
    
    # Resolve the model folder path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(script_dir)
    full_model_dir = os.path.join(backend_dir, args.model_dir)
    
    if not os.path.isdir(full_model_dir):
        # Check relative to current working directory
        full_model_dir = os.path.abspath(args.model_dir)
        if not os.path.isdir(full_model_dir):
            print(f"Error: Model directory '{args.model_dir}' not found.")
            return

    # Files to upload
    files_to_upload = [
        "google_gemma-4-E4B-it-Q5_K_M.gguf",
        "mmproj-google_gemma-4-E4B-it-f16.gguf"
    ]
    
    success = True
    for filename in files_to_upload:
        local_file_path = os.path.join(full_model_dir, filename)
        # We upload them into the root of the file share or in a subfolder. 
        # Let's upload directly to the root of the share to match Llama.cpp setup.
        if os.path.exists(local_file_path):
            file_success = upload_with_progress(
                conn_str=args.conn_string,
                share_name=args.share_name,
                local_path=local_file_path
            )
            if not file_success:
                success = False
        else:
            print(f"Warning: File '{filename}' not found in '{full_model_dir}', skipping.")
            
    if success:
        print("\nAll files uploaded successfully to Azure Storage!")
    else:
        print("\nSome uploads failed. Please check the logs.")

if __name__ == "__main__":
    main()
