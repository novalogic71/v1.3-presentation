#!/usr/bin/env python3
"""
Supervisor Event Listener for Process Monitoring

Listens for process state changes and can trigger notifications
or automatic recovery actions when processes fail.
"""

import sys
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler('/app/logs/process_events.log')
    ]
)
logger = logging.getLogger(__name__)


def write_stdout(s):
    """Write to stdout for supervisor protocol."""
    sys.stdout.write(s)
    sys.stdout.flush()


def write_stderr(s):
    """Write to stderr for logging."""
    sys.stderr.write(s)
    sys.stderr.flush()


def handle_event(event_name, headers, payload):
    """Handle supervisor events."""
    process_name = headers.get('processname', 'unknown')
    group_name = headers.get('groupname', 'unknown')
    
    timestamp = datetime.utcnow().isoformat()
    
    if event_name in ('PROCESS_STATE_FATAL', 'PROCESS_STATE_EXITED'):
        # Parse payload for additional info
        payload_dict = dict(x.split(':') for x in payload.split() if ':' in x)
        exit_code = payload_dict.get('expected', 'unknown')
        
        message = f"[{timestamp}] ALERT: Process {process_name} ({group_name}) - {event_name}"
        logger.error(message)
        
        # You could add notification logic here:
        # - Send email
        # - Send Slack notification
        # - Write to external monitoring system
        
        # Example: Write to a status file that can be monitored externally
        status_file = '/app/logs/process_status.json'
        try:
            import json
            status = {
                'timestamp': timestamp,
                'event': event_name,
                'process': process_name,
                'group': group_name,
                'status': 'UNHEALTHY'
            }
            with open(status_file, 'w') as f:
                json.dump(status, f)
        except Exception as e:
            logger.error(f"Could not write status file: {e}")


def main():
    """Main event loop following supervisor protocol."""
    while True:
        # Transition from ACKNOWLEDGED to READY
        write_stdout('READY\n')
        
        # Read header line
        line = sys.stdin.readline()
        
        # Parse header
        headers = dict(x.split(':') for x in line.split() if ':' in x)
        
        # Read payload
        payload_length = int(headers.get('len', 0))
        payload = sys.stdin.read(payload_length) if payload_length else ''
        
        # Handle the event
        event_name = headers.get('eventname', 'UNKNOWN')
        handle_event(event_name, headers, payload)
        
        # Transition from BUSY to ACKNOWLEDGED
        write_stdout('RESULT 2\nOK')


if __name__ == '__main__':
    main()

