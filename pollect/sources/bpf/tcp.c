// Copyright 2016 Netflix, Inc.
// Licensed under the Apache License, Version 2.0 (the "License")
//
// 02-Sep-2016   Brendan Gregg   Created this.

#include <uapi/linux/ptrace.h>
#include <net/sock.h>
#include <bcc/proto.h>

struct ipv4_key_t {
    u32 pid;
    char name[TASK_COMM_LEN];
    u32 saddr;
    u32 daddr;
    u16 lport;
    u16 dport;
};
BPF_HASH(ipv4_send_bytes, struct ipv4_key_t);
BPF_HASH(ipv4_recv_bytes, struct ipv4_key_t);

struct ipv6_key_t {
    unsigned __int128 saddr;
    unsigned __int128 daddr;
    u32 pid;
    char name[TASK_COMM_LEN];
    u16 lport;
    u16 dport;
    u64 __pad__;
};
BPF_HASH(ipv6_send_bytes, struct ipv6_key_t);
BPF_HASH(ipv6_recv_bytes, struct ipv6_key_t);
BPF_HASH(sock_store, u32, struct sock *);

static int tcp_sendstat(int size)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u32 tid = bpf_get_current_pid_tgid();
    struct sock **sockpp;
    sockpp = sock_store.lookup(&tid);
    if (sockpp == 0) {
        return 0;
    }

    struct sock *sk = *sockpp;
    u16 dport = 0, family;
    bpf_probe_read_kernel(&family, sizeof(family),
        &sk->__sk_common.skc_family);

    if (family == AF_INET) {
        struct ipv4_key_t ipv4_key = {.pid = pid};
        bpf_get_current_comm(&ipv4_key.name, sizeof(ipv4_key.name));
        bpf_probe_read_kernel(&ipv4_key.saddr, sizeof(ipv4_key.saddr),
            &sk->__sk_common.skc_rcv_saddr);
        bpf_probe_read_kernel(&ipv4_key.daddr, sizeof(ipv4_key.daddr),
            &sk->__sk_common.skc_daddr);
        bpf_probe_read_kernel(&ipv4_key.lport, sizeof(ipv4_key.lport),
            &sk->__sk_common.skc_num);
        bpf_probe_read_kernel(&dport, sizeof(dport),
            &sk->__sk_common.skc_dport);
        ipv4_key.dport = ntohs(dport);
        ipv4_send_bytes.increment(ipv4_key, size);

    } else if (family == AF_INET6) {
        struct ipv6_key_t ipv6_key = {.pid = pid};
        bpf_get_current_comm(&ipv6_key.name, sizeof(ipv6_key.name));
        bpf_probe_read_kernel(&ipv6_key.saddr, sizeof(ipv6_key.saddr),
            &sk->__sk_common.skc_v6_rcv_saddr.in6_u.u6_addr32);
        bpf_probe_read_kernel(&ipv6_key.daddr, sizeof(ipv6_key.daddr),
            &sk->__sk_common.skc_v6_daddr.in6_u.u6_addr32);
        bpf_probe_read_kernel(&ipv6_key.lport, sizeof(ipv6_key.lport),
            &sk->__sk_common.skc_num);
        bpf_probe_read_kernel(&dport, sizeof(dport),
            &sk->__sk_common.skc_dport);
        ipv6_key.dport = ntohs(dport);
        ipv6_send_bytes.increment(ipv6_key, size);
    }
    sock_store.delete(&tid);

    // else drop
    return 0;
}

int tcp_send_ret(struct pt_regs *ctx)
{
    int size = PT_REGS_RC(ctx);
    if (size > 0)
        return tcp_sendstat(size);

	return 0;
}

int tcp_send_entry(struct pt_regs *ctx, struct sock *sk)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u32 tid = bpf_get_current_pid_tgid();
    u16 family = sk->__sk_common.skc_family;
    sock_store.update(&tid, &sk);
    return 0;
}

/*
 * tcp_recvmsg() would be obvious to trace, but is less suitable because:
 * - we'd need to trace both entry and return, to have both sock and size
 * - misses tcp_read_sock() traffic
 * we'd much prefer tracepoints once they are available.
 */
int tcp_cleanup_rbuf(struct pt_regs *ctx, struct sock *sk, int copied)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;

    u16 dport = 0, family = sk->__sk_common.skc_family;
    u64 *val, zero = 0;

    if (copied <= 0)
        return 0;

    if (family == AF_INET) {
        struct ipv4_key_t ipv4_key = {.pid = pid};
        bpf_get_current_comm(&ipv4_key.name, sizeof(ipv4_key.name));
        ipv4_key.saddr = sk->__sk_common.skc_rcv_saddr;
        ipv4_key.daddr = sk->__sk_common.skc_daddr;
        ipv4_key.lport = sk->__sk_common.skc_num;
        dport = sk->__sk_common.skc_dport;
        ipv4_key.dport = ntohs(dport);
        ipv4_recv_bytes.increment(ipv4_key, copied);

    } else if (family == AF_INET6) {
        struct ipv6_key_t ipv6_key = {.pid = pid};
        bpf_get_current_comm(&ipv6_key.name, sizeof(ipv6_key.name));
        bpf_probe_read_kernel(&ipv6_key.saddr, sizeof(ipv6_key.saddr),
            &sk->__sk_common.skc_v6_rcv_saddr.in6_u.u6_addr32);
        bpf_probe_read_kernel(&ipv6_key.daddr, sizeof(ipv6_key.daddr),
            &sk->__sk_common.skc_v6_daddr.in6_u.u6_addr32);
        ipv6_key.lport = sk->__sk_common.skc_num;
        dport = sk->__sk_common.skc_dport;
        ipv6_key.dport = ntohs(dport);
        ipv6_recv_bytes.increment(ipv6_key, copied);
    }

    // else drop
    return 0;
}