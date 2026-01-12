#!/usr/bin/env python3
"""
Custom middleware for the FastAPI application.
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown")
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": round(process_time, 3),
                    "client_ip": request.client.host if request.client else "unknown"
                }
            )
            
            # Add processing time header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "process_time": round(process_time, 3),
                    "client_ip": request.client.host if request.client else "unknown"
                },
                exc_info=True
            )
            
            raise

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
        self.last_reset = time.time()
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        current_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        
        # Skip rate limiting for localhost - needed for batch processing UI
        if client_ip in ("127.0.0.1", "localhost", "::1"):
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = "unlimited"
            response.headers["X-RateLimit-Remaining"] = "unlimited"
            return response
        
        # Reset counters every minute
        if current_time - self.last_reset >= 60:
            self.request_counts.clear()
            self.last_reset = current_time
        
        # Check rate limit
        if client_ip in self.request_counts:
            if self.request_counts[client_ip] >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return Response(
                    content="Rate limit exceeded. Please try again later.",
                    status_code=429,
                    headers={"Retry-After": "60"}
                )
            self.request_counts[client_ip] += 1
        else:
            self.request_counts[client_ip] = 1
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers (use .get() to handle race condition during reset)
        current_count = self.request_counts.get(client_ip, 0)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_minute - current_count)
        )
        response.headers["X-RateLimit-Reset"] = str(int(self.last_reset + 60))
        
        return response
