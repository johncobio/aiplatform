from aiplatform.state import Release, StateStore


def test_record_and_rollback_candidate(tmp_path):
    store = StateStore(tmp_path)
    assert store.load("dev", "demo").current is None

    store.record("dev", "demo", Release(tag="t1", image="img:t1", target="local", endpoint="e"))
    store.record("dev", "demo", Release(tag="t2", image="img:t2", target="local", endpoint="e"))
    st = store.load("dev", "demo")
    assert st.current.tag == "t2"
    assert st.previous().tag == "t1"
    assert [r.tag for r in st.releases] == ["t1", "t2"]


def test_history_is_capped(tmp_path):
    store = StateStore(tmp_path, keep=3)
    for i in range(5):
        store.record("dev", "demo", Release(tag=f"t{i}", image="x", target="local", endpoint=""))
    assert [r.tag for r in store.load("dev", "demo").releases] == ["t2", "t3", "t4"]


def test_clear_current_keeps_history(tmp_path):
    store = StateStore(tmp_path)
    store.record("dev", "demo", Release(tag="t1", image="x", target="local", endpoint=""))
    store.clear_current("dev", "demo")
    st = store.load("dev", "demo")
    assert st.current is None
    assert len(st.releases) == 1
