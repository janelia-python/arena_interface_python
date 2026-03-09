from arena_interface import ArenaInterface


def test_bench_metadata_reports_socket_policy() -> None:
    ai = ArenaInterface(tcp_nodelay=False, tcp_quickack=False, socket_timeout_s=3.0)
    meta = ai.bench_metadata(label="unit-test")
    ai.close()

    assert meta["label"] == "unit-test"
    assert meta["tcp_nodelay"] is False
    assert meta["tcp_quickack_requested"] is False
    assert "tcp_quickack_supported" in meta
    assert "socket_keepalive" in meta
    assert meta["socket_timeout_s"] == 3.0
    assert meta["serial_timeout_s"] is None
