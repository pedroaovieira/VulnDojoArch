"""
Core utilities for the vulnerability dashboard.
"""
import time
import logging
import requests
from typing import Optional, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class NVDAPIClient:
    """
    Handles NVD API interactions with rate limiting.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the NVD API client.
        
        Args:
            api_key: Optional NVD API key for higher rate limits
        """
        self.api_key = api_key or settings.NVD_API_KEY
        self.base_url = settings.NVD_API_BASE_URL
        
        # Rate limiting configuration
        # Without API key: 5 requests per 30 seconds
        # With API key: 50 requests per 30 seconds
        self.rate_limit = settings.NVD_RATE_LIMIT_REQUESTS if self.api_key else 5
        self.rate_window = settings.NVD_RATE_LIMIT_WINDOW
        
        self.session = requests.Session()
        self.request_times = []
        
        # Set up headers
        if self.api_key:
            self.session.headers.update({'apiKey': self.api_key})
    
    def _handle_rate_limit(self):
        """
        Implement rate limiting logic with exponential backoff.
        """
        current_time = time.time()
        
        # Remove requests older than the rate window
        self.request_times = [
            t for t in self.request_times 
            if current_time - t < self.rate_window
        ]
        
        # If we've hit the rate limit, wait
        if len(self.request_times) >= self.rate_limit:
            oldest_request = self.request_times[0]
            wait_time = self.rate_window - (current_time - oldest_request)
            
            if wait_time > 0:
                logger.info(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                # Clear old requests after waiting
                self.request_times = []
        
        # Record this request
        self.request_times.append(time.time())
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a rate-limited request to the NVD API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.RequestException: If the request fails
        """
        self._handle_rate_limit()
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            logger.debug(f"Making request to {url} with params {params}")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limit hit, implement exponential backoff
                logger.warning("Rate limit exceeded, implementing exponential backoff")
                time.sleep(60)  # Wait 1 minute before retry
                return self._make_request(endpoint, params)
            else:
                logger.error(f"HTTP error occurred: {e}")
                raise
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def get_cpes(self, start_index: int = 0, results_per_page: int = 2000) -> Dict[str, Any]:
        """
        Fetch CPE data with pagination.
        
        Args:
            start_index: Starting index for pagination
            results_per_page: Number of results per page (max 10000)
            
        Returns:
            JSON response containing CPE data
        """
        params = {
            'startIndex': start_index,
            'resultsPerPage': min(results_per_page, 10000),
        }
        
        return self._make_request('cpes/2.0', params)
    
    def get_cves(self, start_index: int = 0, results_per_page: int = 2000, **filters) -> Dict[str, Any]:
        """
        Fetch CVE data with pagination and filtering.
        
        Args:
            start_index: Starting index for pagination
            results_per_page: Number of results per page (max 2000)
            **filters: Additional filter parameters (e.g., pubStartDate, pubEndDate)
            
        Returns:
            JSON response containing CVE data
        """
        params = {
            'startIndex': start_index,
            'resultsPerPage': min(results_per_page, 2000),
        }
        params.update(filters)
        
        return self._make_request('cves/2.0', params)