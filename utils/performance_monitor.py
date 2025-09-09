import psutil
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    network_sent_mb: float
    network_recv_mb: float
    active_connections: int
    response_times: Dict[str, float]
    api_call_counts: Dict[str, int]
    error_counts: Dict[str, int]
    opportunities_found: int
    uptime_seconds: float


class PerformanceMonitor:
    """Monitors system and application performance"""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics_history: List[PerformanceMetrics] = []
        self.max_history_size = 1000
        
        # Counters
        self.api_calls = {}
        self.error_counts = {}
        self.response_times = {}
        self.opportunities_count = 0
        
        # Network baseline
        self.network_baseline = self._get_network_stats()
    
    def _get_network_stats(self) -> Dict:
        """Get current network statistics"""
        try:
            stats = psutil.net_io_counters()
            return {
                'bytes_sent': stats.bytes_sent,
                'bytes_recv': stats.bytes_recv
            }
        except Exception:
            return {'bytes_sent': 0, 'bytes_recv': 0}
    
    def record_api_call(self, platform: str, endpoint: str = None):
        """Record an API call"""
        key = f"{platform}_{endpoint}" if endpoint else platform
        self.api_calls[key] = self.api_calls.get(key, 0) + 1
    
    def record_response_time(self, operation: str, response_time: float):
        """Record response time for an operation"""
        if operation not in self.response_times:
            self.response_times[operation] = []
        
        self.response_times[operation].append(response_time)
        
        # Keep only last 100 measurements per operation
        if len(self.response_times[operation]) > 100:
            self.response_times[operation] = self.response_times[operation][-100:]
    
    def record_error(self, component: str, error_type: str = None):
        """Record an error occurrence"""
        key = f"{component}_{error_type}" if error_type else component
        self.error_counts[key] = self.error_counts.get(key, 0) + 1
    
    def record_opportunities_found(self, count: int):
        """Record number of opportunities found"""
        self.opportunities_count += count
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network metrics
            current_network = self._get_network_stats()
            network_sent_mb = (current_network['bytes_sent'] - self.network_baseline['bytes_sent']) / 1024 / 1024
            network_recv_mb = (current_network['bytes_recv'] - self.network_baseline['bytes_recv']) / 1024 / 1024
            
            # Connection count
            try:
                connections = len(psutil.net_connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                connections = 0
            
            # Average response times
            avg_response_times = {}
            for operation, times in self.response_times.items():
                if times:
                    avg_response_times[operation] = sum(times) / len(times)
            
            # Uptime
            uptime = time.time() - self.start_time
            
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / 1024 / 1024,
                disk_usage_percent=disk.percent,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                active_connections=connections,
                response_times=avg_response_times,
                api_call_counts=self.api_calls.copy(),
                error_counts=self.error_counts.copy(),
                opportunities_found=self.opportunities_count,
                uptime_seconds=uptime
            )
            
            # Store in history
            self.metrics_history.append(metrics)
            
            # Limit history size
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history = self.metrics_history[-self.max_history_size:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            # Return default metrics
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                disk_usage_percent=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                active_connections=0,
                response_times={},
                api_call_counts={},
                error_counts={},
                opportunities_found=0,
                uptime_seconds=time.time() - self.start_time
            )
    
    def get_performance_summary(self, hours: int = 24) -> Dict:
        """Get performance summary for the last N hours"""
        if not self.metrics_history:
            current_metrics = self.get_current_metrics()
            return self._metrics_to_summary(current_metrics)
        
        # Filter metrics for the specified time period
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            recent_metrics = [self.metrics_history[-1]]  # Use latest if no recent data
        
        # Calculate averages and statistics
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        disk_values = [m.disk_usage_percent for m in recent_metrics]
        
        # Aggregate API calls and errors
        total_api_calls = {}
        total_errors = {}
        
        for metrics in recent_metrics:
            for api, count in metrics.api_call_counts.items():
                total_api_calls[api] = total_api_calls.get(api, 0) + count
            
            for error, count in metrics.error_counts.items():
                total_errors[error] = total_errors.get(error, 0) + count
        
        # Response time analysis
        response_time_summary = {}
        for metrics in recent_metrics:
            for operation, avg_time in metrics.response_times.items():
                if operation not in response_time_summary:
                    response_time_summary[operation] = []
                response_time_summary[operation].append(avg_time)
        
        # Calculate final averages for response times
        for operation in response_time_summary:
            times = response_time_summary[operation]
            response_time_summary[operation] = {
                'avg': sum(times) / len(times),
                'min': min(times),
                'max': max(times),
                'count': len(times)
            }
        
        return {
            'period_hours': hours,
            'metrics_count': len(recent_metrics),
            'system_performance': {
                'cpu_avg': sum(cpu_values) / len(cpu_values),
                'cpu_max': max(cpu_values),
                'memory_avg': sum(memory_values) / len(memory_values),
                'memory_max': max(memory_values),
                'disk_usage': disk_values[-1] if disk_values else 0,
            },
            'network_activity': {
                'total_sent_mb': sum(m.network_sent_mb for m in recent_metrics),
                'total_recv_mb': sum(m.network_recv_mb for m in recent_metrics),
            },
            'api_activity': {
                'total_calls': sum(total_api_calls.values()),
                'calls_by_api': total_api_calls,
                'response_times': response_time_summary
            },
            'error_summary': {
                'total_errors': sum(total_errors.values()),
                'errors_by_type': total_errors
            },
            'business_metrics': {
                'total_opportunities': sum(m.opportunities_found for m in recent_metrics),
                'avg_opportunities_per_hour': sum(m.opportunities_found for m in recent_metrics) / max(hours, 1)
            },
            'uptime': {
                'seconds': recent_metrics[-1].uptime_seconds if recent_metrics else 0,
                'formatted': self._format_uptime(recent_metrics[-1].uptime_seconds if recent_metrics else 0)
            }
        }
    
    def _metrics_to_summary(self, metrics: PerformanceMetrics) -> Dict:
        """Convert single metrics to summary format"""
        return {
            'period_hours': 0,
            'metrics_count': 1,
            'system_performance': {
                'cpu_avg': metrics.cpu_percent,
                'cpu_max': metrics.cpu_percent,
                'memory_avg': metrics.memory_percent,
                'memory_max': metrics.memory_percent,
                'disk_usage': metrics.disk_usage_percent,
            },
            'network_activity': {
                'total_sent_mb': metrics.network_sent_mb,
                'total_recv_mb': metrics.network_recv_mb,
            },
            'api_activity': {
                'total_calls': sum(metrics.api_call_counts.values()),
                'calls_by_api': metrics.api_call_counts,
                'response_times': {k: {'avg': v, 'min': v, 'max': v, 'count': 1} 
                                 for k, v in metrics.response_times.items()}
            },
            'error_summary': {
                'total_errors': sum(metrics.error_counts.values()),
                'errors_by_type': metrics.error_counts
            },
            'business_metrics': {
                'total_opportunities': metrics.opportunities_found,
                'avg_opportunities_per_hour': 0
            },
            'uptime': {
                'seconds': metrics.uptime_seconds,
                'formatted': self._format_uptime(metrics.uptime_seconds)
            }
        }
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_health_status(self) -> Dict:
        """Get current health status"""
        try:
            current_metrics = self.get_current_metrics()
            
            # Health thresholds
            health_issues = []
            
            if current_metrics.cpu_percent > 80:
                health_issues.append(f"High CPU usage: {current_metrics.cpu_percent:.1f}%")
            
            if current_metrics.memory_percent > 85:
                health_issues.append(f"High memory usage: {current_metrics.memory_percent:.1f}%")
            
            if current_metrics.disk_usage_percent > 90:
                health_issues.append(f"High disk usage: {current_metrics.disk_usage_percent:.1f}%")
            
            # Check for recent errors
            recent_errors = sum(current_metrics.error_counts.values())
            if recent_errors > 10:
                health_issues.append(f"High error count: {recent_errors}")
            
            # Check response times
            for operation, avg_time in current_metrics.response_times.items():
                if avg_time > 30:  # 30 seconds threshold
                    health_issues.append(f"Slow response time for {operation}: {avg_time:.1f}s")
            
            status = 'healthy' if not health_issues else 'warning' if len(health_issues) <= 2 else 'critical'
            
            return {
                'status': status,
                'timestamp': datetime.now().isoformat(),
                'uptime': self._format_uptime(current_metrics.uptime_seconds),
                'issues': health_issues,
                'metrics': asdict(current_metrics)
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'uptime': self._format_uptime(time.time() - self.start_time),
                'issues': [f"Health check error: {e}"],
                'metrics': {}
            }
    
    def reset_counters(self):
        """Reset performance counters"""
        self.api_calls.clear()
        self.error_counts.clear()
        self.response_times.clear()
        self.opportunities_count = 0
        logger.info("Performance counters reset")
    
    def save_metrics_to_file(self, filepath: str):
        """Save metrics history to file"""
        try:
            with open(filepath, 'w') as f:
                metrics_data = [asdict(m) for m in self.metrics_history]
                json.dump(metrics_data, f, indent=2, default=str)
            logger.info(f"Metrics saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    def load_metrics_from_file(self, filepath: str):
        """Load metrics history from file"""
        try:
            with open(filepath, 'r') as f:
                metrics_data = json.load(f)
                
            self.metrics_history = []
            for data in metrics_data:
                # Convert timestamp string back to datetime
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                self.metrics_history.append(PerformanceMetrics(**data))
                
            logger.info(f"Loaded {len(self.metrics_history)} metrics from {filepath}")
        except FileNotFoundError:
            logger.info(f"Metrics file {filepath} not found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance"""
    return performance_monitor


async def start_background_monitoring(interval_seconds: int = 300):
    """Start background performance monitoring"""
    logger.info(f"Starting background performance monitoring (interval: {interval_seconds}s)")
    
    while True:
        try:
            performance_monitor.get_current_metrics()
            await asyncio.sleep(interval_seconds)
        except Exception as e:
            logger.error(f"Background monitoring error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry
