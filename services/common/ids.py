import secrets


def new_id(prefix: str, n_bytes: int = 6) -> str:
    """med_a1b2c3, job_x7y8z9, vm_f00d12 style ids."""
    return f"{prefix}_{secrets.token_hex(n_bytes)}"
