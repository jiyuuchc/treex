import typing as tp
from inspect import signature

import jax
import jax.numpy as jnp
import jax.tree_util
import numpy as np

import treex as tx
from treex.types import Initializer

Parameter = tp.cast(tp.Type[np.ndarray], tx.Parameter)
State = tp.cast(tp.Type[tp.Union[np.ndarray, int]], tx.State)


class Linear(tx.Module):
    w: Parameter
    b: Parameter
    n: State

    def __init__(self, din, dout, name="linear"):

        self.din = din
        self.dout = dout
        self.w = np.random.uniform(size=(din, dout))
        self.b = np.random.uniform(size=(dout,))
        self.n = 1
        self.name = name


class MLP(tx.Module):
    linear1: Linear
    linear2: Linear

    def __init__(self, din, dmid, dout, name="mlp"):
        self.din = din
        self.dmid = dmid
        self.dout = dout
        self.name = name

        self.linear1 = Linear(din, dmid, name="linear1")
        self.linear2 = Linear(dmid, dout, name="linear2")


class TestTreex:
    def test_flatten_nothing(self):
        x = [(1, 2), (3, tx.Nothing())]
        assert jax.tree_leaves(x) == [1, 2, 3]

        flat_with_nothing = jax.tree_flatten(x, lambda x: isinstance(x, tx.Nothing))[0]

        assert flat_with_nothing == [1, 2, 3, tx.Nothing()]

    def test_flatten(self):

        mlp = MLP(2, 3, 5)

        flat = jax.tree_leaves(mlp)

        assert len(flat) == 6

    def test_flatten_slice(self):

        mlp = MLP(2, 3, 5).filter(State)

        flat = jax.tree_leaves(mlp)

        assert len(flat) == 2

    def test_flatten_slice_merging(self):

        mlp = MLP(2, 3, 5).filter(State)

        flat = jax.tree_flatten(mlp, lambda x: isinstance(x, tx.Nothing))[0]

        assert len(flat) == 6

    def test_is_tree(self):

        mlp = MLP(2, 3, 5)

        @jax.jit
        def idfn(x):
            return x

        assert not isinstance(mlp.linear1.w, jnp.DeviceArray)
        assert not isinstance(mlp.linear1.b, jnp.DeviceArray)
        assert not isinstance(mlp.linear1.n, jnp.DeviceArray)

        assert not isinstance(mlp.linear2.w, jnp.DeviceArray)
        assert not isinstance(mlp.linear2.b, jnp.DeviceArray)
        assert not isinstance(mlp.linear1.n, jnp.DeviceArray)

        mlp = idfn(mlp)

        assert isinstance(mlp.linear1.w, jnp.DeviceArray)
        assert isinstance(mlp.linear1.b, jnp.DeviceArray)
        assert isinstance(mlp.linear1.n, jnp.DeviceArray)

        assert isinstance(mlp.linear2.w, jnp.DeviceArray)
        assert isinstance(mlp.linear2.b, jnp.DeviceArray)
        assert isinstance(mlp.linear2.n, jnp.DeviceArray)

    def test_filter(self):

        mlp = MLP(2, 3, 5)

        # params
        mlp_params = mlp.filter(Parameter)

        assert not isinstance(mlp_params.linear1.w, tx.Nothing)
        assert not isinstance(mlp_params.linear1.b, tx.Nothing)
        assert isinstance(mlp_params.linear1.n, tx.Nothing)

        assert not isinstance(mlp_params.linear2.w, tx.Nothing)
        assert not isinstance(mlp_params.linear2.b, tx.Nothing)
        assert isinstance(mlp_params.linear2.n, tx.Nothing)

        # states
        mlp_states = mlp.filter(State)

        assert isinstance(mlp_states.linear1.w, tx.Nothing)
        assert isinstance(mlp_states.linear1.b, tx.Nothing)
        assert not isinstance(mlp_states.linear1.n, tx.Nothing)

        assert isinstance(mlp_states.linear2.w, tx.Nothing)
        assert isinstance(mlp_states.linear2.b, tx.Nothing)
        assert not isinstance(mlp_states.linear2.n, tx.Nothing)

    def test_update(self):

        mlp = MLP(2, 3, 5)

        mlp_params = mlp.filter(Parameter)
        mlp_states = mlp.filter(State)

        mlp_next = mlp_params.update(mlp_states)

        assert not isinstance(mlp_next.linear1.w, tx.Nothing)
        assert not isinstance(mlp_next.linear1.b, tx.Nothing)
        assert not isinstance(mlp_next.linear1.n, tx.Nothing)

        assert not isinstance(mlp_next.linear2.w, tx.Nothing)
        assert not isinstance(mlp_next.linear2.b, tx.Nothing)
        assert not isinstance(mlp_next.linear2.n, tx.Nothing)

    def test_update_inplace(self):

        mlp = MLP(2, 3, 5)

        mlp_params = mlp.filter(Parameter)
        mlp_states = mlp.filter(State)

        mlp_params.update(mlp_states, inplace=True)

        assert not isinstance(mlp_params.linear1.w, tx.Nothing)
        assert not isinstance(mlp_params.linear1.b, tx.Nothing)
        assert not isinstance(mlp_params.linear1.n, tx.Nothing)

        assert not isinstance(mlp_params.linear2.w, tx.Nothing)
        assert not isinstance(mlp_params.linear2.b, tx.Nothing)
        assert not isinstance(mlp_params.linear2.n, tx.Nothing)

    def test_update_not_inplace(self):

        mlp = MLP(2, 3, 5)

        mlp_params = mlp.filter(Parameter)
        mlp_states = mlp.filter(State)

        mlp_params.update(mlp_states)

        assert not isinstance(mlp_params.linear1.w, tx.Nothing)
        assert not isinstance(mlp_params.linear1.b, tx.Nothing)
        assert isinstance(mlp_params.linear1.n, tx.Nothing)

        assert not isinstance(mlp_params.linear2.w, tx.Nothing)
        assert not isinstance(mlp_params.linear2.b, tx.Nothing)
        assert isinstance(mlp_params.linear2.n, tx.Nothing)

    def test_list(self):
        class LinearList(tx.Module):
            params: tp.List[Parameter]

            def __init__(self, din, dout, name="linear"):

                self.din = din
                self.dout = dout
                self.params = [
                    np.random.uniform(size=(din, dout)),
                    np.random.uniform(size=(dout,)),
                ]
                self.name = name

        linear = LinearList(2, 3, name="mlp")

        @jax.jit
        def idfn(x):
            return x

        assert not isinstance(linear.params[0], jnp.DeviceArray)
        assert not isinstance(linear.params[1], jnp.DeviceArray)

        linear = idfn(linear)

        assert isinstance(linear.params[0], jnp.DeviceArray)
        assert isinstance(linear.params[1], jnp.DeviceArray)

    def test_treelist(self):
        class MLP(tx.Module):
            linears: tp.List[Linear]

            def __init__(self, din, dmid, dout, name="mlp"):
                self.linears = [
                    Linear(din, dmid, name="linear1"),
                    Linear(dmid, dout, name="linear2"),
                ]

        mlp = MLP(2, 3, 5)

        @jax.jit
        def idfn(x):
            return x

        assert not isinstance(mlp.linears[0].w, jnp.DeviceArray)
        assert not isinstance(mlp.linears[0].b, jnp.DeviceArray)
        assert not isinstance(mlp.linears[0].n, jnp.DeviceArray)

        assert not isinstance(mlp.linears[1].w, jnp.DeviceArray)
        assert not isinstance(mlp.linears[1].b, jnp.DeviceArray)
        assert not isinstance(mlp.linears[1].n, jnp.DeviceArray)

        mlp = idfn(mlp)

        assert isinstance(mlp.linears[0].w, jnp.DeviceArray)
        assert isinstance(mlp.linears[0].b, jnp.DeviceArray)
        assert isinstance(mlp.linears[0].n, jnp.DeviceArray)

        assert isinstance(mlp.linears[1].w, jnp.DeviceArray)
        assert isinstance(mlp.linears[1].b, jnp.DeviceArray)
        assert isinstance(mlp.linears[1].n, jnp.DeviceArray)

    def test_idenpotent_init(self):
        n = 0

        class A(tx.Module):
            def module_init(self, key):
                nonlocal n
                n = n + 1

        module = A()

        module = module.init(42)
        module = module.init(42)

        assert n == 1

    def test_initialized(self):
        class A(tx.Module):
            def module_init(self, key):
                self.x = 420

        module = A()
        assert not module.initialized

        module = module.init(42)

        assert module.x == 420
        assert module.initialized

    def test_initialized_inplace(self):
        class A(tx.Module):
            def module_init(self, key):
                self.x = 420

        module = A()
        assert not module.initialized

        module.init(42, inplace=True)

        assert module.x == 420
        assert module.initialized

    def test_train(self):

        mlp = MLP(2, 3, 5).init(42)

        assert mlp.training
        assert mlp.linear1.training
        assert mlp.linear2.training

        mlp = mlp.eval()

        assert not mlp.training
        assert not mlp.linear1.training
        assert not mlp.linear2.training

        mlp = mlp.train()

        assert mlp.training
        assert mlp.linear1.training
        assert mlp.linear2.training

    def test_train_inplace(self):

        mlp = MLP(2, 3, 5).init(42)

        assert mlp.training
        assert mlp.linear1.training
        assert mlp.linear2.training

        mlp.eval(inplace=True)

        assert not mlp.training
        assert not mlp.linear1.training
        assert not mlp.linear2.training

        mlp.train(inplace=True)

        assert mlp.training
        assert mlp.linear1.training
        assert mlp.linear2.training

    def test_multiple_initializers(self):
        class MLP(tx.Module):
            linear1: tx.Linear
            linear2: tx.Linear

            def __init__(self, din, dmid, dout, name="mlp"):
                self.linear1 = tx.Linear(din, dmid)
                self.linear2 = tx.Linear(dmid, dout)

        mlp = MLP(2, 3, 5).init(42)

    def test_repr(self):
        class MyModule(tx.Module):
            a: tp.Dict[str, tp.List[MLP]]
            b: tp.List[tx.Parameter]

            def __init__(self):
                self.a = {"mlps": [MLP(2, 3, 5), MLP(2, 3, 5)]}
                self.b = [
                    tx.Initializer(lambda key: jnp.zeros((10, 4))),
                    jnp.zeros((5, 13)),
                ]

        mlp = MyModule()  # .init(42)
        mlp = jax.tree_map(
            lambda x: jnp.asarray(x) if not isinstance(x, tx.Initializer) else x, mlp
        )
        mlp = mlp.filter(tx.Parameter)

        rep = repr(mlp)

        rep

    def test_tabulate(self):
        class MyModule(tx.Module):
            a: tp.Dict[str, tp.List[MLP]]
            b: tp.List[tx.Parameter]

            def __init__(self):
                self.a = {"mlps": [MLP(256, 1024, 512), MLP(256, 1024, 512)]}
                self.b = [
                    tx.Initializer(lambda key: jnp.zeros((512, 256))),
                    jnp.zeros((512, 128)),
                ]

        mlp = MyModule()  # .init(42)
        mlp = jax.tree_map(
            lambda x: jnp.asarray(x) if not isinstance(x, tx.Initializer) else x, mlp
        )
        # mlp = mlp.filter(tx.Parameter)

        rep = mlp.tabulate()

        print(rep)

        print(mlp.a["mlps"][1].linear2)
