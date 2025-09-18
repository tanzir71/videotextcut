"""Progress tracking and status updates for long-running operations."""

import threading
import time
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class OperationStatus(Enum):
    """Status of a long-running operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressInfo:
    """Information about operation progress."""
    operation_id: str
    status: OperationStatus
    progress_percent: float = 0.0
    current_step: str = ""
    total_steps: int = 0
    current_step_number: int = 0
    start_time: float = 0.0
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    result: Optional[Any] = None
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time == 0:
            return 0.0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time
    
    @property
    def estimated_remaining_time(self) -> Optional[float]:
        """Estimate remaining time based on current progress."""
        if self.progress_percent <= 0 or self.elapsed_time <= 0:
            return None
        
        total_estimated = self.elapsed_time / (self.progress_percent / 100)
        return max(0, total_estimated - self.elapsed_time)


class ProgressTracker:
    """Thread-safe progress tracker for long-running operations."""
    
    def __init__(self):
        self._operations: Dict[str, ProgressInfo] = {}
        self._callbacks: Dict[str, list] = {}  # operation_id -> list of callbacks
        self._lock = threading.Lock()
        self._cancelled_operations = set()
    
    def start_operation(self, operation_id: str, total_steps: int = 0, 
                       description: str = "") -> ProgressInfo:
        """Start tracking a new operation.
        
        Args:
            operation_id: Unique identifier for the operation
            total_steps: Total number of steps in the operation
            description: Description of the operation
        
        Returns:
            ProgressInfo object for the operation
        """
        with self._lock:
            progress_info = ProgressInfo(
                operation_id=operation_id,
                status=OperationStatus.RUNNING,
                current_step=description,
                total_steps=total_steps,
                start_time=time.time()
            )
            
            self._operations[operation_id] = progress_info
            self._cancelled_operations.discard(operation_id)
            
            # Notify callbacks
            self._notify_callbacks(operation_id, progress_info)
            
            return progress_info
    
    def update_progress(self, operation_id: str, progress_percent: float = None,
                       current_step: str = None, current_step_number: int = None) -> bool:
        """Update progress for an operation.
        
        Args:
            operation_id: Operation identifier
            progress_percent: Progress percentage (0-100)
            current_step: Description of current step
            current_step_number: Current step number
        
        Returns:
            False if operation was cancelled, True otherwise
        """
        with self._lock:
            if operation_id not in self._operations:
                return False
            
            if operation_id in self._cancelled_operations:
                self._operations[operation_id].status = OperationStatus.CANCELLED
                return False
            
            progress_info = self._operations[operation_id]
            
            if progress_percent is not None:
                progress_info.progress_percent = max(0, min(100, progress_percent))
            
            if current_step is not None:
                progress_info.current_step = current_step
            
            if current_step_number is not None:
                progress_info.current_step_number = current_step_number
                # Auto-calculate progress if total_steps is known
                if progress_info.total_steps > 0 and progress_percent is None:
                    progress_info.progress_percent = (current_step_number / progress_info.total_steps) * 100
            
            # Notify callbacks
            self._notify_callbacks(operation_id, progress_info)
            
            return True
    
    def complete_operation(self, operation_id: str, result: Any = None) -> None:
        """Mark an operation as completed.
        
        Args:
            operation_id: Operation identifier
            result: Optional result of the operation
        """
        with self._lock:
            if operation_id not in self._operations:
                return
            
            progress_info = self._operations[operation_id]
            progress_info.status = OperationStatus.COMPLETED
            progress_info.progress_percent = 100.0
            progress_info.end_time = time.time()
            progress_info.result = result
            
            # Notify callbacks
            self._notify_callbacks(operation_id, progress_info)
    
    def fail_operation(self, operation_id: str, error_message: str) -> None:
        """Mark an operation as failed.
        
        Args:
            operation_id: Operation identifier
            error_message: Error description
        """
        with self._lock:
            if operation_id not in self._operations:
                return
            
            progress_info = self._operations[operation_id]
            progress_info.status = OperationStatus.FAILED
            progress_info.end_time = time.time()
            progress_info.error_message = error_message
            
            # Notify callbacks
            self._notify_callbacks(operation_id, progress_info)
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel an operation.
        
        Args:
            operation_id: Operation identifier
        
        Returns:
            True if operation was cancelled, False if not found or already finished
        """
        with self._lock:
            if operation_id not in self._operations:
                return False
            
            progress_info = self._operations[operation_id]
            
            if progress_info.status in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
                return False
            
            self._cancelled_operations.add(operation_id)
            progress_info.status = OperationStatus.CANCELLED
            progress_info.end_time = time.time()
            
            # Notify callbacks
            self._notify_callbacks(operation_id, progress_info)
            
            return True
    
    def get_progress(self, operation_id: str) -> Optional[ProgressInfo]:
        """Get current progress information for an operation.
        
        Args:
            operation_id: Operation identifier
        
        Returns:
            ProgressInfo object or None if operation not found
        """
        with self._lock:
            return self._operations.get(operation_id)
    
    def is_cancelled(self, operation_id: str) -> bool:
        """Check if an operation has been cancelled.
        
        Args:
            operation_id: Operation identifier
        
        Returns:
            True if operation is cancelled
        """
        with self._lock:
            return operation_id in self._cancelled_operations
    
    def add_callback(self, operation_id: str, callback: Callable[[ProgressInfo], None]) -> None:
        """Add a callback to be notified of progress updates.
        
        Args:
            operation_id: Operation identifier
            callback: Function to call with ProgressInfo updates
        """
        with self._lock:
            if operation_id not in self._callbacks:
                self._callbacks[operation_id] = []
            self._callbacks[operation_id].append(callback)
    
    def remove_callback(self, operation_id: str, callback: Callable[[ProgressInfo], None]) -> None:
        """Remove a progress callback.
        
        Args:
            operation_id: Operation identifier
            callback: Callback function to remove
        """
        with self._lock:
            if operation_id in self._callbacks:
                try:
                    self._callbacks[operation_id].remove(callback)
                except ValueError:
                    pass  # Callback not found
    
    def _notify_callbacks(self, operation_id: str, progress_info: ProgressInfo) -> None:
        """Notify all callbacks for an operation (called with lock held).
        
        Args:
            operation_id: Operation identifier
            progress_info: Current progress information
        """
        callbacks = self._callbacks.get(operation_id, [])
        
        # Call callbacks in separate threads to avoid blocking
        for callback in callbacks:
            try:
                threading.Thread(
                    target=callback,
                    args=(progress_info,),
                    daemon=True
                ).start()
            except Exception:
                pass  # Ignore callback errors
    
    def cleanup_completed_operations(self, max_age_seconds: float = 3600) -> None:
        """Clean up old completed operations.
        
        Args:
            max_age_seconds: Maximum age for completed operations to keep
        """
        current_time = time.time()
        
        with self._lock:
            operations_to_remove = []
            
            for operation_id, progress_info in self._operations.items():
                if (progress_info.status in [OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED] and
                    progress_info.end_time and
                    current_time - progress_info.end_time > max_age_seconds):
                    operations_to_remove.append(operation_id)
            
            for operation_id in operations_to_remove:
                del self._operations[operation_id]
                self._callbacks.pop(operation_id, None)
                self._cancelled_operations.discard(operation_id)
    
    def get_all_operations(self) -> Dict[str, ProgressInfo]:
        """Get all current operations.
        
        Returns:
            Dictionary of operation_id -> ProgressInfo
        """
        with self._lock:
            return self._operations.copy()
    
    def get_active_operations(self) -> Dict[str, ProgressInfo]:
        """Get all currently active (running) operations.
        
        Returns:
            Dictionary of operation_id -> ProgressInfo for active operations
        """
        with self._lock:
            return {
                op_id: info for op_id, info in self._operations.items()
                if info.status == OperationStatus.RUNNING
            }


# Global progress tracker instance
_global_tracker = ProgressTracker()


def get_global_tracker() -> ProgressTracker:
    """Get the global progress tracker instance.
    
    Returns:
        Global ProgressTracker instance
    """
    return _global_tracker


# Convenience functions for common operations
def start_operation(operation_id: str, total_steps: int = 0, description: str = "") -> ProgressInfo:
    """Start tracking a new operation using the global tracker."""
    return _global_tracker.start_operation(operation_id, total_steps, description)


def update_progress(operation_id: str, progress_percent: float = None,
                   current_step: str = None, current_step_number: int = None) -> bool:
    """Update progress for an operation using the global tracker."""
    return _global_tracker.update_progress(operation_id, progress_percent, current_step, current_step_number)


def complete_operation(operation_id: str, result: Any = None) -> None:
    """Mark an operation as completed using the global tracker."""
    _global_tracker.complete_operation(operation_id, result)


def fail_operation(operation_id: str, error_message: str) -> None:
    """Mark an operation as failed using the global tracker."""
    _global_tracker.fail_operation(operation_id, error_message)


def cancel_operation(operation_id: str) -> bool:
    """Cancel an operation using the global tracker."""
    return _global_tracker.cancel_operation(operation_id)


def get_progress(operation_id: str) -> Optional[ProgressInfo]:
    """Get current progress information using the global tracker."""
    return _global_tracker.get_progress(operation_id)


def is_cancelled(operation_id: str) -> bool:
    """Check if an operation has been cancelled using the global tracker."""
    return _global_tracker.is_cancelled(operation_id)