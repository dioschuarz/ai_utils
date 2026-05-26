"""
OpenTelemetry context utilities for MCP _meta field propagation.

This module provides utilities for propagating trace context through MCP's _meta field,
enabling linked traces between the LangGraph client and MCP servers.

CRITICAL: This uses OpenTelemetry context.attach() to properly propagate trace context,
ensuring that @observe decorators create child spans within the parent trace.

Based on: https://github.com/langfuse/langfuse-examples/tree/main/applications/mcp-tracing
Reference: https://langfuse.com/docs/observability/features/mcp-tracing
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def parse_traceparent(traceparent: str) -> Optional[Dict[str, str]]:
    """
    Parse W3C traceparent header into components.
    
    Format: version-traceid-parentid-traceflags
    Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
    
    Args:
        traceparent: W3C Trace Context traceparent string
        
    Returns:
        Dictionary with version, trace_id, parent_id, trace_flags or None
    """
    try:
        parts = traceparent.split("-")
        if len(parts) == 4:
            return {
                "version": parts[0],
                "trace_id": parts[1],
                "parent_id": parts[2],
                "trace_flags": parts[3],
            }
    except Exception:
        pass
    return None


def extract_otel_context_from_meta(meta: Optional[Dict[str, Any]] = None):
    """
    Extract OpenTelemetry context from MCP _meta field.
    
    The _meta field may contain traceparent, tracestate, and baggage
    following W3C Trace Context specification.
    
    Args:
        meta: Dictionary containing trace context fields from MCP request
        
    Returns:
        OpenTelemetry Context object with extracted trace context
    """
    try:
        from opentelemetry import context
        from opentelemetry.propagate import get_global_textmap
        
        if not meta:
            return context.get_current()
        
        # Create a carrier dict with the trace context fields
        carrier: Dict[str, str] = {}
        if "traceparent" in meta:
            carrier["traceparent"] = meta["traceparent"]
        if "tracestate" in meta:
            carrier["tracestate"] = meta["tracestate"]
        if "baggage" in meta:
            carrier["baggage"] = meta["baggage"]
        
        # Extract context using OpenTelemetry's propagator
        if carrier:
            propagator = get_global_textmap()
            extracted_ctx = propagator.extract(carrier)
            logger.debug(f"Extracted OTEL context from _meta: traceparent={carrier.get('traceparent', 'N/A')}")
            return extracted_ctx
        
        return context.get_current()
    except ImportError:
        logger.debug("opentelemetry not available, returning None context")
        return None
    except Exception as e:
        logger.warning(f"Failed to extract OTEL context: {e}")
        return None


def with_otel_context_from_meta(func: F) -> F:
    """
    Decorator that extracts OpenTelemetry context from MCP request _meta field
    and ATTACHES it as the current context before executing the function.
    
    CRITICAL: This uses context.attach() which makes @observe decorators
    create child spans within the parent trace, instead of separate traces.
    
    This decorator expects the decorated function to receive _meta through kwargs
    (injected by MCP JSON-RPC arguments). It extracts and removes _meta before
    calling the actual function.
    
    Usage:
        @mcp.tool()
        @with_otel_context_from_meta
        @observe(name="my_tool")
        async def my_tool(arg1: str) -> str:
            # This function now runs within the propagated trace context
            return "result"
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function that activates the context from _meta
    """
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        # Extract _meta from kwargs (but DON'T remove it - let the function handle it)
        meta = kwargs.get("_meta")
        
        # Try to attach OpenTelemetry context
        token = None
        try:
            from opentelemetry import context
            ctx = extract_otel_context_from_meta(meta)
            if ctx is not None:
                token = context.attach(ctx)
                logger.debug(f"Attached OTEL context for {func.__name__}")
        except ImportError:
            logger.debug("opentelemetry not available, skipping context attach")
        except Exception as e:
            logger.warning(f"Failed to attach OTEL context: {e}")
        
        try:
            return func(*args, **kwargs)
        finally:
            if token is not None:
                try:
                    from opentelemetry import context
                    context.detach(token)
                    logger.debug(f"Detached OTEL context for {func.__name__}")
                except Exception as e:
                    logger.warning(f"Failed to detach OTEL context: {e}")
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # Extract _meta from kwargs
        meta = kwargs.get("_meta")
        
        # Try to attach OpenTelemetry context
        token = None
        try:
            from opentelemetry import context
            ctx = extract_otel_context_from_meta(meta)
            if ctx is not None:
                token = context.attach(ctx)
                logger.debug(f"Attached OTEL context for {func.__name__}")
        except ImportError:
            logger.debug("opentelemetry not available, skipping context attach")
        except Exception as e:
            logger.warning(f"Failed to attach OTEL context: {e}")
        
        try:
            return await func(*args, **kwargs)
        finally:
            if token is not None:
                try:
                    from opentelemetry import context
                    context.detach(token)
                    logger.debug(f"Detached OTEL context for {func.__name__}")
                except Exception as e:
                    logger.warning(f"Failed to detach OTEL context: {e}")
    
    # Return appropriate wrapper based on function type
    if asyncio.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    else:
        return sync_wrapper  # type: ignore
