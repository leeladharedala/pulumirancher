import pulumi
import pulumi_aws as aws
import pulumi_command as command

# Read the public key from the specified file
with open("/Users/leeladharedala/pulumirancher/keys/key3.pub", 'r') as key_file:
    public_key = key_file.read().strip()

# Read the private key from the specified file
with open("/Users/leeladharedala/pulumirancher/keys/key3.pem", 'r') as key_file:
    private_key = key_file.read().strip()

# Create a key pair for SSH access
key_pair = aws.ec2.KeyPair("rke2-key", public_key=public_key)

# Create a security group to allow SSH and HTTPS access
security_group = aws.ec2.SecurityGroup("rke2-security-group",
    description="Allow all traffic",
    ingress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]},
    ],
    egress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]},
    ]
)

# Create an EC2 instance for RKE2 and Rancher
rke2_instance = aws.ec2.Instance("rke2-instance",
    instance_type="t3.medium",
    ami="ami-0866a3c8686eaeeba",  # Update this if needed
    key_name=key_pair.key_name,
    security_groups=[security_group.name],
    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        volume_size=30 
    ),
    tags={"Name": "RKE2Server"}
)

# Install RKE2 server on the EC2 instance
install_rke2 = command.remote.Command("install-rke2",
    connection=command.remote.ConnectionArgs(
        host=rke2_instance.public_ip,
        user="ubuntu",
        private_key=private_key
    ),
    create="""
    #!/bin/bash
    # Update packages
    sudo yum update -y
    
    # Configure passwordless sudo for ec2-user
    sudo su

    # Install RKE2 server
    curl -sfL https://get.rke2.io | sudo sh -
    sudo systemctl enable rke2-server
    sudo systemctl start rke2-server

    # Wait for RKE2 to be ready
    sleep 90
    
    # Install kubectl
    sudo curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

    # Configure kubeconfig
    sudo mkdir -p /root/.kube
    sudo cp /etc/rancher/rke2/rke2.yaml /root/.kube/config
    sudo chown ubuntu:ubuntu /etc/rancher/rke2/rke2.yaml 
    export KUBECONFIG=/etc/rancher/rke2/rke2.yaml

    # Install Helm
    curl -#L https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

    # Add Rancher Helm repo
    helm repo add rancher-latest https://releases.rancher.com/server-charts/latest
    helm repo add jetstack https://charts.jetstack.io

    # Install cert-manager
    kubectl apply -f https://github.com/jetstack/cert-manager/releases/download/v1.6.1/cert-manager.crds.yaml
    helm upgrade -i cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace

    # Install Rancher
    helm upgrade -i rancher rancher-latest/rancher --create-namespace --namespace cattle-system --set hostname=rancher.dockr.life --set bootstrapPassword=bootStrapAllTheThings --set replicas=1

    # Check the namespace
    kubectl -n cattle-system get pods
    """,
    opts=pulumi.ResourceOptions(depends_on=[rke2_instance])
)

# Export the public IP of the RKE2 instance
pulumi.export("rke2_instance_public_ip", rke2_instance.public_ip)