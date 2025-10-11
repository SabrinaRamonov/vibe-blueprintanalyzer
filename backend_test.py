import requests
import sys
import os
import io
from datetime import datetime
from PIL import Image
import base64

class BlueprintAPITester:
    def __init__(self, base_url="https://blueprint-calc-4.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details
        })

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'N/A')}"
            self.log_test("Root Endpoint", success, details)
            return success
        except Exception as e:
            self.log_test("Root Endpoint", False, str(e))
            return False

    def test_status_endpoints(self):
        """Test status check endpoints"""
        try:
            # Test POST /status
            test_data = {"client_name": f"test_client_{datetime.now().strftime('%H%M%S')}"}
            response = requests.post(f"{self.base_url}/status", json=test_data, timeout=10)
            
            post_success = response.status_code == 200
            self.log_test("POST Status", post_success, f"Status: {response.status_code}")
            
            # Test GET /status
            response = requests.get(f"{self.base_url}/status", timeout=10)
            get_success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if get_success:
                data = response.json()
                details += f", Count: {len(data) if isinstance(data, list) else 'N/A'}"
            
            self.log_test("GET Status", get_success, details)
            return post_success and get_success
            
        except Exception as e:
            self.log_test("Status Endpoints", False, str(e))
            return False

    def create_test_image(self):
        """Create a simple test image"""
        # Create a simple blueprint-like image
        img = Image.new('RGB', (800, 600), color='white')
        # Save to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()

    def test_analyze_blueprint_with_image(self):
        """Test blueprint analysis with a test image"""
        try:
            # Create test image
            image_data = self.create_test_image()
            
            # Prepare file upload
            files = {
                'file': ('test_blueprint.png', image_data, 'image/png')
            }
            
            print("🔍 Testing blueprint analysis (this may take 30-60 seconds for AI processing)...")
            response = requests.post(
                f"{self.base_url}/analyze-blueprint", 
                files=files, 
                timeout=120  # 2 minute timeout for AI processing
            )
            
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                # Check response structure
                required_fields = ['success', 'filename', 'analysis', 'original_image', 'annotated_image']
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    success = False
                    details += f", Missing fields: {missing_fields}"
                else:
                    # Check analysis structure
                    analysis = data.get('analysis', {})
                    analysis_fields = ['scale', 'scale_confidence', 'dimensions', 'notes']
                    analysis_details = []
                    
                    for field in analysis_fields:
                        if field in analysis:
                            if field == 'dimensions':
                                analysis_details.append(f"dimensions: {len(analysis[field])}")
                            else:
                                analysis_details.append(f"{field}: {analysis[field]}")
                    
                    details += f", Analysis: {', '.join(analysis_details)}"
                    
                    # Check if images are base64 encoded
                    if data.get('original_image', '').startswith('data:image/'):
                        details += ", Original image: ✓"
                    else:
                        details += ", Original image: ❌"
                        
                    if data.get('annotated_image', '').startswith('data:image/'):
                        details += ", Annotated image: ✓"
                    else:
                        details += ", Annotated image: ❌"
            else:
                try:
                    error_data = response.json()
                    details += f", Error: {error_data.get('detail', 'Unknown error')}"
                except:
                    details += f", Response: {response.text[:200]}"
            
            self.log_test("Analyze Blueprint (Image)", success, details)
            return success
            
        except Exception as e:
            self.log_test("Analyze Blueprint (Image)", False, str(e))
            return False

    def test_invalid_file_upload(self):
        """Test error handling for invalid file types"""
        try:
            # Create a text file (invalid type)
            invalid_data = b"This is not an image or PDF file"
            files = {
                'file': ('test.txt', invalid_data, 'text/plain')
            }
            
            response = requests.post(f"{self.base_url}/analyze-blueprint", files=files, timeout=30)
            
            # Should return an error (4xx or 5xx)
            success = response.status_code >= 400
            details = f"Status: {response.status_code}"
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    details += f", Error handled: {error_data.get('detail', 'Unknown error')}"
                except:
                    details += ", Error response received"
            
            self.log_test("Invalid File Type Handling", success, details)
            return success
            
        except Exception as e:
            self.log_test("Invalid File Type Handling", False, str(e))
            return False

    def test_get_analyses(self):
        """Test getting all analyses"""
        try:
            response = requests.get(f"{self.base_url}/analyses", timeout=10)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                details += f", Count: {len(data) if isinstance(data, list) else 'N/A'}"
            
            self.log_test("GET Analyses", success, details)
            return success
            
        except Exception as e:
            self.log_test("GET Analyses", False, str(e))
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Blueprint API Backend Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test basic endpoints first
        print("\n📋 Testing Basic Endpoints...")
        self.test_root_endpoint()
        self.test_status_endpoints()
        self.test_get_analyses()
        
        # Test main functionality
        print("\n🔬 Testing Main Functionality...")
        self.test_analyze_blueprint_with_image()
        
        # Test error handling
        print("\n⚠️  Testing Error Handling...")
        self.test_invalid_file_upload()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("❌ Some tests failed. Check details above.")
            failed_tests = [test for test in self.test_results if not test['success']]
            print("\nFailed Tests:")
            for test in failed_tests:
                print(f"  - {test['name']}: {test['details']}")
            return False

def main():
    tester = BlueprintAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())