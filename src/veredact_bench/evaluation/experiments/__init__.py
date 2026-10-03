"""One runner per manuscript experiment; ids match configs/experiments/<id>.yaml. Each exposes run(cfg, out)."""

from . import (
    exp00_primitives,
    exp01_redaction_throughput,
    exp02_authorization_latency,
    exp03_audit_efficiency,
    exp04_verification_time,
    exp05_gas_consumption,
)

RUNNERS = {
    m.__name__.rsplit(".", 1)[1]: m.run
    for m in (
        exp00_primitives,
        exp01_redaction_throughput,
        exp02_authorization_latency,
        exp03_audit_efficiency,
        exp04_verification_time,
        exp05_gas_consumption,
    )
}
