#include <linux/bpf.h>
#include <linux/ip.h>
#include <linux/ipv6.h>
#include <linux/tcp.h>

struct ip_details
{
    unsigned int srcIp;
    unsigned int dstIp;
    unsigned int bytes;
    unsigned int protocol;
};

BPF_RINGBUF_OUTPUT(events, 128);

int count_network_bytes_per_ip(struct xdp_md *ctx)
{
    // We mark the start and end of our ethernet frame
    void *ethernet_start = (void *)(long)ctx->data;
    void *ethernet_end = (void *)(long)ctx->data_end;

    if (ethernet_start + sizeof(struct ethhdr) > ethernet_end)
    {
		return XDP_PASS;
	}

    struct ethhdr *ethernet_frame = ethernet_start;
	unsigned int ethernet_size_in_bytes = (ethernet_end - ethernet_start);

    // Check if we have the entire ethernet frame
	unsigned int ipType = bpf_ntohs(ethernet_frame->h_proto);
	if(ipType == ETH_P_IP)
	{
		struct iphdr *ip_packet = ethernet_start + sizeof(*ethernet_frame);

		// Check if the IP packet is within the bounds of ethernet frame
		if ((void *)ip_packet + sizeof(*ip_packet) <= ethernet_end)
		{
			struct ip_details *ip_and_byte = events.ringbuf_reserve(sizeof(struct ip_details));
			if (!ip_and_byte)
			{
				return 1;
			}
			ip_and_byte->srcIp = (unsigned int) bpf_ntohl(ip_packet->saddr);
			ip_and_byte->dstIp = (unsigned int) bpf_ntohl(ip_packet->daddr);
			ip_and_byte->bytes = ethernet_size_in_bytes;
			ip_and_byte->protocol = ip_packet->protocol;
			events.ringbuf_submit(ip_and_byte, 0);
		}
		return XDP_PASS;
	}
	if(ipType == ETH_P_IPV6)
	{
		struct ipv6hdr *ip_packet = ethernet_start + sizeof(*ethernet_frame);

		// Check if the IP packet is within the bounds of ethernet frame
		if ((void *)ip_packet + sizeof(*ip_packet) <= ethernet_end)
		{
			struct ip_details *ip_and_byte = events.ringbuf_reserve(sizeof(struct ip_details));
			if (!ip_and_byte)
			{
				return 1;
			}

			ip_and_byte->srcIp = (unsigned int) 0;
			ip_and_byte->dstIp = (unsigned int) 0;
			ip_and_byte->bytes = ethernet_size_in_bytes;
			ip_and_byte->protocol = 0;
			events.ringbuf_submit(ip_and_byte, 0);
		}
		return XDP_PASS;
	}
    return XDP_PASS;
}