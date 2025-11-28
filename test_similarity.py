"""Test script for similarity functionality.

Note: Make sure you have API keys configured in your environment:
- OPENAI_API_KEY or ADAPTER_OPENAI_API_KEY for OpenAI (REQUIRED for embeddings)
- GOOGLE_API_KEY or GEMINI_API_KEY for Gemini
- GROQ_API_KEY or ADAPTER_GROQ_API_KEY for Groq
"""
import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
import httpx

# Load .env file
load_dotenv()

BASE_URL = "http://localhost:8001"


def check_api_keys() -> bool:
    """Check if required API keys are configured."""
    openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("ADAPTER_OPENAI_API_KEY")
    if not openai_key:
        print("WARNING: OpenAI API key not found!")
        print("   Embedding generation requires OPENAI_API_KEY or ADAPTER_OPENAI_API_KEY")
        print("   Set it with: $env:OPENAI_API_KEY='your-key' (PowerShell)")
        print("   Or create a .env file with: OPENAI_API_KEY=your-key")
        return False
    return True


async def test_similarity_workflow() -> None:
    """Test the complete similarity workflow."""
    
    # Step 1: Register/Login to get authentication token
    print("Step 1: Authenticating...")
    async with httpx.AsyncClient() as client:
        # Test credentials
        test_email = "test@example.com"
        test_password = "testpassword123"
        
        # Try to register first (will fail if user exists, that's okay)
        try:
            register_response = await client.post(
                f"{BASE_URL}/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": test_password,
                    "name": "Test User"
                }
            )
            if register_response.status_code == 200:
                print("✓ Registered new test user")
            # If user exists, continue to login
        except Exception:
            pass  # Continue to login attempt
        
        # Now try to login
        login_data = {
            "email": test_email,
            "password": test_password
        }
        
        try:
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=login_data
            )
            if login_response.status_code != 200:
                print(f"Login failed: {login_response.text}")
                print("Please check your credentials or register manually")
                return
            
            token_data = login_response.json()
            # Try different response structures
            access_token = (
                token_data.get("data", {}).get("token") or
                token_data.get("data", {}).get("access_token") or
                token_data.get("token") or
                token_data.get("access_token")
            )
            if not access_token:
                print(f"Failed to get access token. Response: {token_data}")
                return
            
            headers = {"Authorization": f"Bearer {access_token}"}
            print("[OK] Authentication successful")
        except Exception as e:
            print(f"Authentication error: {e}")
            print("Note: Similarity endpoints require authentication")
            return
        
        # Step 2: Generate LLM responses
        print("\nStep 2: Generating LLM responses...")
        multi_llm_request = {
            "prompt": "What is artificial intelligence? Explain in 2-3 sentences.",
            "adapter_ids": ["openai", "gemini", "groq"]  # Using real adapters
        }
        
        try:
            multi_llm_response = await client.post(
                f"{BASE_URL}/api/v1/multi-llm/collect",
                json=multi_llm_request
            )
            multi_llm_response.raise_for_status()
            multi_llm_data = multi_llm_response.json()
            request_id = multi_llm_data.get("request_id")
            
            if not request_id:
                print("Failed to get request_id from multi-LLM response")
                return
            
            print(f"[OK] Generated responses with request_id: {request_id}")
            print(f"  Total responses: {multi_llm_data.get('total_responses')}")
            print(f"  Successful: {multi_llm_data.get('successful_responses')}")
            print(f"  Failed: {multi_llm_data.get('failed_responses')}")
            
            # Show response details
            responses = multi_llm_data.get('responses', [])
            for resp in responses:
                status = "[OK]" if resp.get('success') else "[FAIL]"
                print(f"    {status} {resp.get('adapter_id')}: {resp.get('latency_ms', 0)}ms, {resp.get('tokens', 0)} tokens")
                if not resp.get('success'):
                    print(f"      Error: {resp.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"Error generating responses: {e}")
            return
        
        # Step 3: Process similarity analysis
        print("\nStep 3: Processing similarity analysis...")
        similarity_request = {
            "request_id": request_id,
            "persist": True
        }
        
        try:
            similarity_response = await client.post(
                f"{BASE_URL}/api/v1/similarity/process",
                json=similarity_request,
                headers=headers
            )
            similarity_response.raise_for_status()
            similarity_data = similarity_response.json()
            
            # Response is now SimilarityAnalysisResponse directly, not wrapped
            print("[OK] Similarity analysis completed")
            print(f"\nResults:")
            print(f"  Request ID: {similarity_data.get('request_id')}")
            print(f"\n  Consensus Scores:")
            for provider, score in similarity_data.get("consensus_scores", {}).items():
                print(f"    {provider}: {score:.4f}")
            
            print(f"\n  Outliers: {similarity_data.get('outliers', [])}")
            
            stats = similarity_data.get("statistics", {})
            if isinstance(stats, dict):
                print(f"\n  Statistics:")
                print(f"    Mean: {stats.get('mean', 0):.4f}")
                print(f"    Std Dev: {stats.get('std_dev', 0):.4f}")
                print(f"    Min: {stats.get('min', 0):.4f}")
                print(f"    Max: {stats.get('max', 0):.4f}")
            
            print(f"\n  Similarity Matrix:")
            matrix = similarity_data.get("similarity_matrix", {})
            for provider1, similarities in matrix.items():
                for provider2, score in similarities.items():
                    if provider1 != provider2:
                        print(f"    {provider1} <-> {provider2}: {score:.4f}")
        except httpx.HTTPStatusError as e:
            print(f"Error processing similarity: {e.response.status_code}")
            try:
                error_detail = e.response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
                # Extract the actual error message
                if "detail" in error_detail:
                    detail = error_detail["detail"]
                    if isinstance(detail, dict) and "error" in detail:
                        error_info = detail["error"]
                        print(f"\nError Code: {error_info.get('code', 'UNKNOWN')}")
                        print(f"Error Message: {error_info.get('message', 'No message')}")
            except Exception as parse_error:
                print(f"Error response (raw): {e.response.text}")
                print(f"Failed to parse error: {parse_error}")
            return
        except Exception as e:
            print(f"Error processing similarity: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Step 4: Retrieve stored analysis
        print("\nStep 4: Retrieving stored similarity analysis...")
        try:
            get_response = await client.get(
                f"{BASE_URL}/api/v1/similarity/{request_id}",
                headers=headers
            )
            get_response.raise_for_status()
            get_data = get_response.json()
            
            # Response is now SimilarityAnalysisResponse directly
            print("[OK] Successfully retrieved stored analysis")
            print(f"  Request ID: {get_data.get('request_id')}")
            print(f"  Consensus Scores: {len(get_data.get('consensus_scores', {}))} providers")
            print(f"  Outliers: {len(get_data.get('outliers', []))}")
        except Exception as e:
            print(f"Error retrieving analysis: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Similarity Functionality Test")
    print("=" * 60)
    
    if not check_api_keys():
        print("\nWARNING: Continuing anyway, but embedding generation will fail...")
        print()
    
    asyncio.run(test_similarity_workflow())

