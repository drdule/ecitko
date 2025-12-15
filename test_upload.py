"""
Simple test script to demonstrate the upload endpoint functionality.
This is for demonstration purposes only.

To run tests properly, you would need:
1. A running MySQL database with the required schema
2. FastAPI application running
3. pytest for proper testing

Example manual test:
1. Start the server: uvicorn main:app --reload
2. Use curl or API client to test the endpoint
"""

import requests
from pathlib import Path


def test_upload_endpoint():
    """
    Example of how to test the upload endpoint.
    This requires the server to be running and database to be configured.
    """
    
    # API endpoint
    url = "http://localhost:8000/upload"
    
    # Test data
    consumer_id = 1
    
    # Create a test image file (in real scenario, use an actual image)
    test_image_path = Path("/tmp/test_image.jpg")
    
    # Prepare multipart form data
    files = {
        'file': ('test_image.jpg', open(test_image_path, 'rb'), 'image/jpeg')
    }
    data = {
        'consumerId': consumer_id
    }
    
    try:
        # Send POST request
        response = requests.post(url, files=files, data=data)
        
        # Print response
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Assert successful upload
        assert response.status_code == 200
        assert response.json()['message'] == 'Image uploaded successfully'
        assert 'image_id' in response.json()
        assert 'image_url' in response.json()
        
        print("✓ Test passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")


def test_invalid_file_format():
    """Test with invalid file format"""
    url = "http://localhost:8000/upload"
    
    test_file_path = Path("/tmp/test_file.txt")
    
    files = {
        'file': ('test_file.txt', open(test_file_path, 'rb'), 'text/plain')
    }
    data = {
        'consumerId': 1
    }
    
    try:
        response = requests.post(url, files=files, data=data)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Assert error response
        assert response.status_code == 400
        assert 'Invalid file format' in response.json()['detail']
        
        print("✓ Test passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")


def test_consumer_not_found():
    """Test with non-existent consumer ID"""
    url = "http://localhost:8000/upload"
    
    test_image_path = Path("/tmp/test_image.jpg")
    
    files = {
        'file': ('test_image.jpg', open(test_image_path, 'rb'), 'image/jpeg')
    }
    data = {
        'consumerId': 99999  # Non-existent consumer
    }
    
    try:
        response = requests.post(url, files=files, data=data)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Assert error response
        assert response.status_code == 404
        assert 'not found' in response.json()['detail']
        
        print("✓ Test passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")


if __name__ == "__main__":
    print("Note: These tests require:")
    print("1. The FastAPI server to be running (uvicorn main:app --reload)")
    print("2. MySQL database configured and running")
    print("3. Test image files to exist")
    print("4. requests library installed (pip install requests)")
    print("\nFor production testing, use pytest with proper fixtures.")
