import boto3
from datetime import datetime, timedelta

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')

    # Get all EBS snapshots in the current AWS account
    response = ec2.describe_snapshots(OwnerIds=['self'])

    # Get all active EC2 instance IDs
    instances_response = ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    active_instance_ids = set()

    for reservation in instances_response['Reservations']:
        for instance in reservation['Instances']:
            active_instance_ids.add(instance['InstanceId'])

    # Iterate through and delete snapshots not attached to any volume or older than 30 days
    for snapshot in response['Snapshots']:
        snapshot_id = snapshot['SnapshotId']
        volume_id = snapshot.get('VolumeId')

        if not volume_id:
            # Delete the snapshot if it's not attached to any volume
            try:
                ec2.delete_snapshot(SnapshotId=snapshot_id)
                print(f"Deleted EBS snapshot {snapshot_id} as it was not attached to any volume.")
            except Exception as e:
                print(f"Error deleting snapshot {snapshot_id}: {str(e)}")
        else:
            try:
                # Check if the volume still exists
                volume_response = ec2.describe_volumes(VolumeIds=[volume_id])
                attachments = volume_response['Volumes'][0]['Attachments']

                if not attachments:
                    # Check if the snapshot is older than 30 days
                    snapshot_start_time = snapshot['StartTime'].replace(tzinfo=None)
                    if datetime.utcnow() - snapshot_start_time > timedelta(days=30):
                        ec2.delete_snapshot(SnapshotId=snapshot_id)
                        print(f"Deleted EBS snapshot {snapshot_id} as it was older than 30 days and volume is not attached.")
            except ec2.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'InvalidVolume.NotFound':
                    # The volume associated with the snapshot is not found (it might have been deleted)
                    try:
                        ec2.delete_snapshot(SnapshotId=snapshot_id)
                        print(f"Deleted EBS snapshot {snapshot_id} as its associated volume was not found.")
                    except Exception as ex:
                        print(f"Error deleting snapshot {snapshot_id}: {str(ex)}")
                else:
                    print(f"Error describing volume {volume_id} for snapshot {snapshot_id}: {str(e)}")
