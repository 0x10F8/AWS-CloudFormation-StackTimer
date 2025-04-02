import boto3
from datetime import timedelta
import argparse

# Get the profile and region from command line arguments
parser = argparse.ArgumentParser(description='Get stack information from AWS CloudFormation.')
parser.add_argument('--profile', type=str, required=True, help='AWS profile name')
parser.add_argument('--region', type=str, required=True, help='AWS region name')
args = parser.parse_args()
profile_name = args.profile
region = args.region

session = boto3.session.Session(profile_name=profile_name)
client = session.client('cloudformation', region_name=region)
# List all stacks in the specified AWS account and region
list_stacks_response = client.list_stacks()


def parse_stack_timings(stack_events: list, stack_name: str) -> tuple:
    """
    Parse stack events to get the creation and update times.
    :param stack_events: List of stack events
    :param stack_name: Name of the stack
    :return: Tuple containing creation time and update times
    """
    create_start = "CREATE_IN_PROGRESS"
    create_end = "CREATE_COMPLETE"

    update_start = "UPDATE_IN_PROGRESS"
    update_end = "UPDATE_COMPLETE"

    failed_update_event = "UPDATE_ROLLBACK_COMPLETE"

    create_time = None
    failed_update_count = 0
    update_times = []

    current_event = None
    current_end_time = None

    for event in stack_events:
        if event['LogicalResourceId'] == stack_name:
            if event['ResourceStatus'] == failed_update_event:
                failed_update_count += 1
            if event['ResourceStatus'] == create_end:
                current_event = "CREATE"
                current_end_time = event['Timestamp']
            elif event['ResourceStatus'] == update_end:
                current_event = "UPDATE"
                current_end_time = event['Timestamp']
            elif event['ResourceStatus'] == create_start:
                if current_event == "CREATE":
                    start_time = event['Timestamp']
                    create_time = current_end_time - start_time
                else:
                    raise ValueError("Unexpected event sequence")
            elif event['ResourceStatus'] == update_start:
                if current_event == "UPDATE":
                    start_time = event['Timestamp']
                    update_times.append(current_end_time - start_time)
                else:
                    raise ValueError("Unexpected event sequence")

    return create_time, update_times, failed_update_count

for stack in list_stacks_response['StackSummaries']:

    # Skip stacks that are deleted
    if stack['StackStatus'] == 'DELETE_COMPLETE':
        continue

    stack_name = stack['StackName']

    create_start = "CREATE_IN_PROGRESS"
    create_end = "CREATE_COMPLETE"

    update_start = "UPDATE_IN_PROGRESS"
    update_end = "UPDATE_COMPLETE"

    failed_update_event = "UPDATE_ROLLBACK_COMPLETE"

    create_time = None
    failed_update_count = 0
    update_times = []

    stack_events_response = client.describe_stack_events(StackName=stack_name)
    stack_events = stack_events_response['StackEvents']
    next_token = stack_events_response.get('NextToken', None)
    while next_token:
        stack_events_response = client.describe_stack_events(StackName=stack_name, NextToken=next_token)
        stack_events.extend(stack_events_response['StackEvents'])
        next_token = stack_events_response.get('NextToken', None)

    create_time, update_times, failed_update_count = parse_stack_timings(stack_events, stack_name)
    
    print(f"Stack Name: {stack_name}")
    print(f"Current Status: {stack['StackStatus']}")
    print(f"Creation Time: {stack['CreationTime']}")
    print(f"Last Updated Time: {stack.get('LastUpdatedTime', None)}")
    print(f"Creation Time Taken: {create_time}")
    for i, update_time in enumerate(update_times):
        print(f"Update Time Taken {i + 1}: {update_time}")
    average_update_time = sum(update_times, timedelta()) / len(update_times) if update_times else None
    print(f"Average Update Time Taken: {average_update_time}")
    print(f"Failed Update Count: {failed_update_count}")
    print("-" * 40)