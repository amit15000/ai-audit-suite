"""Test API endpoint with judge evaluation."""
import asyncio
import httpx
import os
import sys
from pathlib import Path

BASE_URL = "http://localhost:8001"


async def test_api_judge():
    """Test the comparison API with judge evaluation."""
    print("=" * 80)
    print("Testing API Endpoint with Judge Evaluation")
    print("=" * 80)
    
    # Step 1: Login
    print("\n1. Logging in...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": "test@example.com", "password": "test123"},
            )
            
            if login_response.status_code != 200:
                print(f"✗ Login failed: {login_response.status_code}")
                print(f"  Response: {login_response.text}")
                return
            
            token = login_response.json()["data"]["access_token"]
            print(f"✓ Login successful")
            
        except Exception as e:
            print(f"✗ Login error: {str(e)}")
            return
        
        # Step 2: Submit comparison
        print("\n2. Submitting comparison...")
        try:
            submit_response = await client.post(
                f"{BASE_URL}/api/v1/comparison/submit",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "prompt": "Explain quantum computing in simple terms",
                    "platforms": ["openai", "gemini"],
                    "judge": "openai",
                },
            )
            
            if submit_response.status_code != 200:
                print(f"✗ Submit failed: {submit_response.status_code}")
                print(f"  Response: {submit_response.text}")
                return
            
            data = submit_response.json()
            comparison_id = data["data"]["comparisonId"]
            print(f"✓ Comparison submitted: {comparison_id}")
            print(f"  Status: {data['data']['status']}")
            
        except Exception as e:
            print(f"✗ Submit error: {str(e)}")
            return
        
        # Step 3: Wait and check status
        print("\n3. Waiting for processing...")
        import time
        max_wait = 120  # 2 minutes
        waited = 0
        check_interval = 3
        
        while waited < max_wait:
            await asyncio.sleep(check_interval)
            waited += check_interval
            
            try:
                status_response = await client.get(
                    f"{BASE_URL}/api/v1/comparison/{comparison_id}/status",
                    headers={"Authorization": f"Bearer {token}"},
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()["data"]
                    progress = status_data.get("progress", 0)
                    status = status_data.get("status", "unknown")
                    
                    print(f"  Progress: {progress}% | Status: {status}")
                    
                    if status == "completed":
                        break
                    elif status == "failed":
                        print(f"✗ Comparison failed")
                        return
                        
            except Exception as e:
                print(f"  Status check error: {str(e)}")
        
        # Step 4: Get results
        print("\n4. Getting results...")
        try:
            results_response = await client.get(
                f"{BASE_URL}/api/v1/comparison/{comparison_id}/results",
                headers={"Authorization": f"Bearer {token}"},
            )
            
            if results_response.status_code != 200:
                print(f"✗ Get results failed: {results_response.status_code}")
                print(f"  Response: {results_response.text}")
                return
            
            results = results_response.json()["data"]
            print(f"✓ Results retrieved")
            
            # Check judge evaluation
            platforms = results.get("platforms", [])
            print(f"\n  Processed {len(platforms)} platforms")
            
            for platform in platforms:
                platform_id = platform.get("id")
                platform_name = platform.get("name")
                score = platform.get("score")
                judge_eval = platform.get("judgeEvaluation")
                
                print(f"\n  Platform: {platform_name} ({platform_id})")
                print(f"    Overall Score: {score}/100")
                
                if judge_eval:
                    print(f"    ✓ Judge Evaluation:")
                    print(f"      Trust Score: {judge_eval.get('trustScore')}/10")
                    scores = judge_eval.get("scores", {})
                    print(f"      Accuracy: {scores.get('accuracy')}/10")
                    print(f"      Completeness: {scores.get('completeness')}/10")
                    print(f"      Clarity: {scores.get('clarity')}/10")
                    print(f"      Reasoning: {scores.get('reasoning')}/10")
                    print(f"      Safety: {scores.get('safety')}/10")
                    print(f"      Hallucination Risk: {scores.get('hallucination_risk')}/10")
                    print(f"      Fallback Applied: {judge_eval.get('fallbackApplied')}")
                else:
                    print(f"    ⚠️  No judge evaluation")
            
            print(f"\n✓ Test completed successfully!")
            
        except Exception as e:
            print(f"✗ Get results error: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("\nStarting API Test...\n")
    asyncio.run(test_api_judge())

