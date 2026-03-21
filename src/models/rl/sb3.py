from __future__ import annotations

from typing import Any, Callable


def make_vec_env(env_fns: list[Callable[[], object]]):
    if not env_fns:
        raise ValueError("At least one environment factory is required.")
    envs = [env_fn() for env_fn in env_fns]
    if len(envs) == 1:
        return envs[0]
    return envs


def build_policy_kwargs(params: dict[str, Any]) -> dict[str, Any]:
    from stable_baselines3.common.torch_layers import FlattenExtractor

    extractor_cfg = dict(params.get("extractor", {}) or {})
    net_arch = params.get("net_arch")
    extractor_kind = str(extractor_cfg.get("kind", "flatten"))
    policy_kwargs: dict[str, Any] = {}
    if extractor_kind == "flatten":
        policy_kwargs["features_extractor_class"] = FlattenExtractor
    else:
        from src.models.rl.extractors import SequenceFeatureExtractor

        policy_kwargs["features_extractor_class"] = SequenceFeatureExtractor
        policy_kwargs["features_extractor_kwargs"] = {
            "kind": extractor_kind,
            "features_dim": int(extractor_cfg.get("features_dim", 64)),
            "hidden_dim": int(extractor_cfg.get("hidden_dim", 64)),
            "num_layers": int(extractor_cfg.get("num_layers", 1)),
            "num_heads": int(extractor_cfg.get("num_heads", 4)),
            "dropout": float(extractor_cfg.get("dropout", 0.1)),
            "conv_channels": tuple(extractor_cfg.get("conv_channels", (32, 64))),
            "kernel_sizes": tuple(extractor_cfg.get("kernel_sizes", (3, 3))),
        }
    if net_arch is not None:
        policy_kwargs["net_arch"] = net_arch
    return policy_kwargs


def train_sb3_model(
    *,
    algorithm: str,
    env,
    observation_space,
    params: dict[str, Any],
    runtime_meta: dict[str, Any],
) -> tuple[object, dict[str, Any]]:
    del observation_space
    algo = str(algorithm).lower()
    if algo not in {"ppo", "dqn"}:
        raise ValueError("algorithm must be 'ppo' or 'dqn'.")

    from stable_baselines3 import DQN, PPO

    policy_kwargs = build_policy_kwargs(params)
    total_timesteps = int(params.get("total_timesteps", 5_000))
    if total_timesteps <= 0:
        raise ValueError("model.params.total_timesteps must be > 0 for RL agents.")

    seed = int(runtime_meta.get("seed", 7))
    policy = str(params.get("policy", "MlpPolicy"))
    learning_rate = float(params.get("learning_rate", 3e-4))
    gamma = float(params.get("gamma", 0.99))
    device = str(params.get("device", "cpu"))
    envs = list(env) if isinstance(env, list) else [env]
    if not envs:
        raise ValueError("At least one training environment is required.")
    first_env = envs[0]

    if algo == "ppo":
        n_steps = max(int(params.get("n_steps", 128)), 2)
        batch_size = max(int(params.get("batch_size", 64)), 1)
        max_batch = max(n_steps, 1)
        batch_size = min(batch_size, max_batch)
        model = PPO(
            policy=policy,
            env=first_env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            gamma=gamma,
            gae_lambda=float(params.get("gae_lambda", 0.95)),
            clip_range=float(params.get("clip_range", 0.2)),
            ent_coef=float(params.get("ent_coef", 0.0)),
            vf_coef=float(params.get("vf_coef", 0.5)),
            max_grad_norm=float(params.get("max_grad_norm", 0.5)),
            policy_kwargs=policy_kwargs,
            seed=seed,
            verbose=0,
            device=device,
        )
        for env_idx, current_env in enumerate(envs):
            if env_idx > 0:
                model.set_env(current_env)
            model.learn(
                total_timesteps=total_timesteps,
                progress_bar=False,
                reset_num_timesteps=env_idx == 0,
            )
        return model, {
            "algorithm": "ppo",
            "policy": policy,
            "total_timesteps": total_timesteps,
            "learning_rate": learning_rate,
            "gamma": gamma,
            "n_steps": n_steps,
            "batch_size": batch_size,
            "seed": seed,
        }

    batch_size = max(int(params.get("batch_size", 64)), 1)
    model = DQN(
        policy=policy,
        env=first_env,
        learning_rate=learning_rate,
        buffer_size=int(params.get("buffer_size", 10_000)),
        learning_starts=int(params.get("learning_starts", 100)),
        batch_size=batch_size,
        tau=float(params.get("tau", 1.0)),
        gamma=gamma,
        train_freq=int(params.get("train_freq", 1)),
        gradient_steps=int(params.get("gradient_steps", 1)),
        target_update_interval=int(params.get("target_update_interval", 100)),
        exploration_fraction=float(params.get("exploration_fraction", 0.3)),
        exploration_initial_eps=float(params.get("exploration_initial_eps", 1.0)),
        exploration_final_eps=float(params.get("exploration_final_eps", 0.05)),
        policy_kwargs=policy_kwargs,
        seed=seed,
        verbose=0,
        device=device,
    )
    for env_idx, current_env in enumerate(envs):
        if env_idx > 0:
            model.set_env(current_env)
        model.learn(
            total_timesteps=total_timesteps,
            progress_bar=False,
            reset_num_timesteps=env_idx == 0,
        )
    return model, {
        "algorithm": "dqn",
        "policy": policy,
        "total_timesteps": total_timesteps,
        "learning_rate": learning_rate,
        "gamma": gamma,
        "batch_size": batch_size,
        "seed": seed,
    }


__all__ = ["build_policy_kwargs", "make_vec_env", "train_sb3_model"]
