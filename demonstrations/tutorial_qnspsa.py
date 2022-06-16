"""
Quantum natural SPSA optimizer
==============================

In this tutorial, we show how one can implement the quantum natural
simultaneous perturbation stochastic approximation (QN-SPSA) optimizer
from Gacon et al. [1] using Pennylane.

"""


######################################################################
# Introduction
# ------------
#
# In quantum machine learning (QML) and variational quantum algorithms
# (VQA), an optimizer does the following two tasks: - It estimates the
# gradient of the cost function and/or other relevant metrics at the
# current step. - Based on the metrics, it decides the parameters for the
# next iteration to reduce the cost.
#
# A simple example of such an optimizer is the vanilla gradient descent
# (GD), the update rule of which is written as:
# :raw-latex:`\begin{equation}
# \mathbf{x}^{(t + 1)} = \mathbf{x}^{(t)} - \eta \nabla f(\mathbf{x}^{(t)}) \label{eq:vanilla}\tag{1}.
# \end{equation}`
#
# Here the gradient :math:`\nabla f` is estimated dimension by dimension,
# requiring :math:`O(d)` quantum measurements (:math:`d` being the
# dimension of the parameter space). As quantum measurements are
# expensive, this scaling makes GD impractical for high-dimensional
# complicated circuits.
#


######################################################################
# To address this unsatisfying scaling, simultaneous perturbation
# stochastic approximation (SPSA) optimizer replaces this dimension-wise
# gradient estimation with a stochastic one [2]. In SPSA, a random
# direction :math:`\mathbf{h} \in \mathcal{U}(\{-1, 1\}^d)` in the
# parameter space is sampled, and the gradient component along this
# sampled direction is measured with a finite difference approach, with a
# perturbation step size :math:`\epsilon`:
#
# .. math::
#
#      |{\nabla}_{\mathbf{h}}f(\mathbf{x})| \equiv
#    \mathbf{h}\cdot {\nabla}f(\mathbf{x}) \simeq \frac{1}{2\epsilon}\big(f(\mathbf{x} + \epsilon \mathbf{h}) - f(\mathbf{x} - \epsilon \mathbf{h})\big)\label{eq:finite_diff}\tag{2}.
#
# A stochastic gradient estimator
# :math:`\widehat{\boldsymbol{\nabla}}f(\mathbf{x}, \mathbf{h})_{SPSA}` is
# then constructed:
#
# .. math:: \widehat{\nabla f}(\mathbf{x}, \mathbf{h})_{SPSA} = | {\nabla}_{\mathbf{h}}f(\mathbf{x})|\mathbf{h}\label{eq:spsaGrad}\tag{3}.
#
# With the estimator, SPSA gives the following update rule:
#
# .. math:: \mathbf{x}^{(t + 1)} = \mathbf{x}^{(t)} - \eta \widehat{\nabla f}(\mathbf{x}^{(t)}, \mathbf{h}^{(t)})_{SPSA} \label{eq:spsa}\tag{4},
#
# where :math:`\mathbf{h}^{(t)}` is sampled at each step. Although this
# stochastic approach cannot provide a step-wise unbiased gradient
# estimation, SPSA is proved to be especially effective when accumulated
# over multiple optimization steps.
#


######################################################################
# On the other hand, quantum natural gradient descent (QNG) is a variant
# of gradient descent. It introduces the Fubini-Study metric tensor
# :math:`\boldsymbol{g}` [3] into the optimization to account for the
# structure of the non-Euclidean parameter space [4]. The
# :math:`d`-by-:math:`d` metric tensor is defined as
#
# .. math:: \boldsymbol{g}_{ij}(\mathbf{x}) = -\frac{1}{2} \frac{\partial}{\partial \mathbf{x}_i} \frac{\partial}{\partial \mathbf{x}_j} F(\mathbf{x}', \mathbf{x})\biggr\rvert_{\mathbf{x}'=\mathbf{x}},\label{eq:fsTensor}\tag{5}
#
# where
# :math:`F(\mathbf{x}', \mathbf{x}) = \bigr\rvert\langle \phi(\mathbf{x}') | \phi(\mathbf{x}) \rangle \bigr\rvert ^ 2`,
# and :math:`\phi(\mathbf{x})` is the parameterized ansatz with input
# :math:`\mathbf{x}`. With the metric tensor, the update rule is rewritten
# as:
#
# .. math:: \mathbf{x}^{(t + 1)} = \mathbf{x}^{(t)} - \eta \boldsymbol{g}^{-1}(\mathbf{x}^{(t)}) \nabla f(\mathbf{x}^{(t)}) \label{eq:qn}\tag{6}.
#
# While the introduction of the metric tensor helps the optimization [5],
# the algorithm is not as scalable due to the number of measurements
# required to estimate :math:`\boldsymbol{g}`.
#


######################################################################
# QN-SPSA manages to combine the merits of both QNG and SPSA by estimating
# both the gradient and the metric tensor stochastically. The gradient is
# estimated in the same fashion as the SPSA algorithm, while the
# Fubini-Study metric is computed by a second-order process with another
# two stochastic perturbations:
#
# .. math:: \widehat{\boldsymbol{g}}(\mathbf{x}, \mathbf{h}_1, \mathbf{h}_2)_{SPSA} = \frac{\delta F }{8 \epsilon^2}\Big(\mathbf{h}_1 \mathbf{h}_2^\intercal + \mathbf{h}_2 \mathbf{h}_1^\intercal\Big) \label{eq:fs_qnspsa}\tag{7},
#
# where
#
# .. math:: \delta F = F(\mathbf{x, \mathbf{x} + \epsilon \mathbf{h}_1} + \epsilon \mathbf{h}_2) - F (\mathbf{x, \mathbf{x} + \epsilon \mathbf{h}_1}) - F(\mathbf{x, \mathbf{x} - \epsilon \mathbf{h}_1} + \epsilon \mathbf{h}_2) + F(\mathbf{x, \mathbf{x} + \epsilon \mathbf{h}_1})\label{eq:deltaf}\tag{8},
#
# and :math:`\mathbf{h}_1, \mathbf{h}_2 \in \mathcal{U}(\{-1, 1\}^d)` are
# two randomly sampled directions.
#
# With Eq. :raw-latex:`\eqref{eq:fs_qnspsa}`, QN-SPSA provides an update
# rule of:
#
# .. math:: \mathbf{x}^{(t + 1)} = \mathbf{x}^{(t)} - \eta \widehat{\boldsymbol{g}}^{-1}(\mathbf{x}^{(t)}, \mathbf{h}_1^{(t)}, \mathbf{h}_2^{(t)})_{SPSA} \widehat{\nabla f}(\mathbf{x}^{(t)}, \mathbf{h}^{(t)})_{SPSA} \label{eq:qnspsa}\tag{9}.
#
# In each optimization step :math:`t`, one will need to randomly sample 3
# perturbation directions
# :math:`\mathbf{h}^{(t)}, \mathbf{h}_1^{(t)}, \mathbf{h}_2^{(t)}`. Eq.
# :raw-latex:`\eqref{eq:qnspsa}` is then applied to compute the parameters
# for the :math:`(t + 1)`\ th step accordingly. This :math:`O(1)` update
# rule fits into NISQ devices well.
#
# Numerical stability
# -------------------
#
# The QN-SPSA update rule given in Eq. :raw-latex:`\eqref{eq:qnspsa}` is
# highly stochastic, and may not behave well numerically. In practice, a
# few tricks are applied to ensure the method’s numerical stability [1]:
#
# Averaging on the Fubini-Study metric tensor
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#
# A running average is taken on the tensor metric estimated from Eq.
# :raw-latex:`\eqref{eq:fs_qnspsa}` at each step :math:`t`:
#
# .. math:: \bar{\boldsymbol{g}}^{(t)}(\mathbf{x}) = \frac{1}{t + 1} \Big(\sum_{i=1}^{t}\widehat{\boldsymbol{g}}(\mathbf{x}, \mathbf{h}_1^{(i)}, \mathbf{h}_2^{(i)})_{SPSA} + \boldsymbol{g}^{(0)}\Big)\label{eq:tensorRunningAvg}\tag{10} ,
#
# where the initial guess :math:`\boldsymbol{g}^{(0)}` is set to be the
# identity matrix.
#
# Fubini-Study metric tensor regularization
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#
# To ensure the positive semi-definite property of the metric tensor near
# a minimum, the running average in Eq.
# :raw-latex:`\eqref{eq:tensorRunningAvg}` is regularized:
#
# .. math:: \bar{\boldsymbol{g}}^{(t)}_{reg}(\mathbf{x}) = \sqrt{\bar{\boldsymbol{g}}^{(t)}(\mathbf{x}) \bar{\boldsymbol{g}}^{(t)}(\mathbf{x})} + \beta \mathbb{1}\label{eq:tensor_reg}\tag{11},
#
# where :math:`\beta` is the regularization coefficient. With Eq.
# :raw-latex:`\eqref{eq:tensor_reg}`, the QN-SPSA update rule we implement
# in code goes as:
#
# .. math:: \mathbf{x}^{(t + 1)} = \mathbf{x}^{(t)} - \eta (\bar{\boldsymbol{g}}^{(t)}_{reg})^{-1}(\mathbf{x}^{(t)}) \widehat{\nabla f}(\mathbf{x}^{(t)}, \mathbf{h}^{(t)})_{SPSA} \label{eq:qnspsa_reg}\tag{12}.
#
# Blocking condition on the parameter update
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#
# A blocking condition is applied onto the parameter update. The optimizer
# only accepts updates that leads to a loss value no larger than the one
# before update, plus a tolerance. Ref. [6] suggests choosing a tolerance
# that is twice the standard deviation of the loss.
#


######################################################################
# Implementation
# --------------
#
# Let’s first set up a toy example to optimize. We use a QAOA max cut
# problem to do so. Refer to `this
# page <https://pennylane.readthedocs.io/en/stable/code/api/pennylane.qaoa.cost.maxcut.html>`__
# for more details.
#

# intialize a graph for the max cut problem
import networkx as nx
from matplotlib import pyplot as plt
import pennylane as qml
from pennylane import qaoa

nodes = n_qubits = 4
edges = 4
seed = 121

g = nx.gnm_random_graph(nodes, edges, seed=seed)
cost_h, mixer_h = qaoa.maxcut(g)
depth = 2
# Defining device to be the pennylane lightning local simulator
dev = qml.device("lightning.qubit", wires=n_qubits, shots=1000)


def qaoa_layer(gamma, alpha):
    qaoa.cost_layer(gamma, cost_h)
    qaoa.mixer_layer(alpha, mixer_h)


def qaoa_circuit(params, n_qubits, depth):
    # initalizing all qubits into +X eigenstate.
    for w in range(n_qubits):
        qml.Hadamard(wires=w)
    gammas = params[0]
    alphas = params[1]
    # stacking building blocks for depth times.
    qml.layer(qaoa_layer, depth, gammas, alphas)


# Defining ansatz and loss function
@qml.qnode(dev)
def cost_function(params):
    qaoa_circuit(params, n_qubits, depth)
    return qml.expval(cost_h)


######################################################################
# Let’s confirm this circuit works.
#

from pennylane import numpy as np

params_curr = 2 * np.pi * (np.random.rand(2, depth) - 0.5)
print("input parameter shape:", params_curr.shape)
print("Loss value:", cost_function(params_curr))


######################################################################
# With the problem set up, we will for now focus on implementing a
# single-step update of the QNSPSA. Given the current parameters
# ``params_curr``, we would like to compute the parameters for the next
# step ``params_next``. We first define a few necessary
# hyperparameters/variables.
#

import random

# step index
k = 1

# random seed for sampling the perturbation directions
seed = 1
random.seed(seed)

# perturbation size for the finite difference calculation
finite_diff_step = 1e-2

# regularization coefficient for the tensor metric
regularization = 1e-3

# learning rate
lr = 1e-2

# initialize the tensor metric to be an identity matrix
params_number = params_curr.size
metric_tensor = np.identity(params_number)


######################################################################
# As both the gradient estimator and the metric tensor estimator involve
# getting random perturbation directions, we first implement this sampling
# function.
#


def get_perturbation_direction(params):
    param_number = len(params) if isinstance(params, list) else params.size
    sample_list = random.choices([-1, 1], k=param_number)
    direction = np.array(sample_list).reshape(params.shape)
    return direction


print(get_perturbation_direction(params_curr))


######################################################################
# With the function, we start with the gradient estimator:
#


def get_grad(params_curr):
    grad_dir = get_perturbation_direction(params_curr)
    # apply the perturbation
    params_forward = params_curr + finite_diff_step * grad_dir
    params_backward = params_curr - finite_diff_step * grad_dir
    # measured stochastic gradient
    loss_forward = cost_function(params_forward)
    loss_backward = cost_function(params_backward)
    grad = (loss_forward - loss_backward) / (2 * finite_diff_step) * grad_dir
    return grad


grad = get_grad(params_curr)
print("Estimated SPSA gradient:\n", grad)


######################################################################
# To estimate the raw stochastic metric tensor, we will first need to
# measure the state overlap
# :math:`F(\mathbf{x}_1, \mathbf{x}_2) = \bigr\rvert\langle \phi(\mathbf{x}_1) | \phi(\mathbf{x}_2) \rangle \bigr\rvert ^ 2`.
# We denote the unitary transformation forming the ansatz with :math:`U`.
# That is,
# :math:`\rvert\phi(\mathbf{x})\rangle = U(\mathbf{x}) \rvert0\rangle`.
# Applying the adjoint operation :math:`U^{\dagger}(\mathbf{x}_2)` on to
# the ansatz state :math:`\rvert\phi(\mathbf{x}_1)\rangle` followed with a
# measurement in the computational basis then does the trick. The state
# overlap equals the probability of a :math:`\rvert00...0\rangle`
# measurement outcome. Note that this circuit measuring the state overlap
# doubles the circuit depth of the ansatz, and therefore has longer
# execution time and experiences more accumulated noises from the device.
#


def get_operations(qnode, params):
    qnode.construct([params], {})
    return qnode.tape.operations


def get_overlap_tape(qnode, params1, params2):
    op_forward = get_operations(qnode, params1)
    op_inv = get_operations(qnode, params2)

    with qml.tape.QuantumTape() as tape:
        for op in op_forward:
            qml.apply(op)
        for op in reversed(op_inv):
            op.adjoint()
        qml.probs(wires=qnode.tape.wires.labels)
    return tape


def get_state_overlap(tape):
    return qml.execute([tape], dev, None)[0][0][0]


######################################################################
# Let’s do a quick sanity check on the state overlap calculation:
#

tape = get_overlap_tape(cost_function, params_curr, params_curr)
print("Perfect overlap: ", get_state_overlap(tape))

tape = get_overlap_tape(cost_function, params_curr, 2 * np.pi * (np.random.rand(2, depth) - 0.5))
print("Random state overlap: ", get_state_overlap(tape))


def get_raw_tensor_metric(params_curr):

    dir1 = get_perturbation_direction(params_curr)
    dir2 = get_perturbation_direction(params_curr)
    perturb1 = dir1 * finite_diff_step
    perturb2 = dir2 * finite_diff_step
    dir_vec1 = dir1.reshape(-1)
    dir_vec2 = dir2.reshape(-1)
    tapes = [
        get_overlap_tape(cost_function, params_curr, params_curr + perturb1 + perturb2),
        get_overlap_tape(cost_function, params_curr, params_curr + perturb1),
        get_overlap_tape(cost_function, params_curr, params_curr - perturb1 + perturb2),
        get_overlap_tape(cost_function, params_curr, params_curr - perturb1),
    ]

    tensor_finite_diff = (
        get_state_overlap(tapes[0])
        - get_state_overlap(tapes[1])
        - get_state_overlap(tapes[2])
        + get_state_overlap(tapes[3])
    )

    metric_tensor_raw = (
        -(np.tensordot(dir_vec1, dir_vec2, axes=0) + np.tensordot(dir_vec2, dir_vec1, axes=0))
        * tensor_finite_diff
        / (8 * finite_diff_step * finite_diff_step)
    )
    return metric_tensor_raw


metric_tensor_raw = get_raw_tensor_metric(params_curr)
print("Raw estimated metric tensor:\n", metric_tensor_raw)


######################################################################
# Apply the running average and regularization tricks:
#

from scipy.linalg import sqrtm

metric_tensor_avg = 1 / (k + 1) * metric_tensor_raw + k / (k + 1) * metric_tensor
tensor_reg = np.real(sqrtm(np.matmul(metric_tensor_avg, metric_tensor_avg)))
# update metric tensor
metric_tensor = ((tensor_reg + regularization * np.identity(metric_tensor.shape[0]))) / (
    1 + regularization
)
# update step index
k += 1
print("Updated metric tensor after the step:\n", metric_tensor)


######################################################################
# Eq. (12) requires computing the inverse of the metric tensor. A
# numerically more stable approach is to solve the equivalent linear
# equation:
#
# .. math:: \bar{\boldsymbol{g}}^{(t)}_{reg}(\mathbf{x}^{(t)})\big( \mathbf{x}^{(t)} - \mathbf{x}^{(t + 1)}\big) =  \eta  \widehat{\nabla f}(\mathbf{x}^{(t)}, \mathbf{h}^{(t)})_{SPSA} \label{eq:lin_solver}\tag{13}.
#


def get_next_params(params, gradient):
    grad_vec, params_vec = gradient.reshape(-1), params.reshape(-1)
    new_params_vec = np.linalg.solve(
        metric_tensor,
        (-lr * grad_vec + np.matmul(metric_tensor, params_vec)),
    )
    return new_params_vec.reshape(params.shape)


params_next = get_next_params(params_curr, grad)
print("Next parameters:\n", params_next)


######################################################################
# Now it is the time to apply the blocking condition. Let’s first try the
# proposal in Ref [6] to use twice the standard deviation of the loss as
# the tolerance. To do so, we will need to repeat the cost function
# measurement for several times. The straightforward implementation goes
# as follows:
#

loss_next = cost_function(params_next)

repeats = 10
loss_curr_list = np.zeros(repeats)
for i in range(repeats):
    loss_curr_list[i] = cost_function(params_curr)

tol = 2 * loss_curr_list.std()
loss_curr = loss_curr_list.mean()

# block updates that leads to significant increase
# of the loss value
if loss_curr + tol < loss_next:
    params_next = params_curr
print("Next parameters after blocking:\n", params_next)


######################################################################
# As quantum measurements are generally expensive, computing the tolerance
# this way adds significant overhead to the QN-SPSA optimizer. To be
# specific, in each step of the optimization, QN-SPSA only requires
# executing 2 circuits for the gradient, and 4 for the tensor metric. Yet
# in the approach above, there are additional 10 (repeat number) + 1
# circuits required to apply the blocking.
#
# To address this issue, we propose to define the tolerance as the
# standard deviation of the loss values of the past :math:`N` steps
# instead. The intuition here is, when the optimizer is working in
# fast-descending regime, the blocking condition is unlikely to be
# triggered, as new loss values are often smaller than the previous ones.
# On the other hand, when the optimizer is working in a rather flat energy
# landscape, losses from the past :math:`N` steps could be very similar to
# the current loss value. In this regime, the tolerance defined from both
# approaches should be close.
#
# The implementation of this tolerance goes as:
#

# defining number of steps to track
history_length = 5
# tracking the past losses in an array
last_n_steps = np.zeros(history_length)


# step-wise update
loss_curr = cost_function(params_curr)
loss_next = cost_function(params_next)

# k has been updated above
ind = (k - 2) % history_length
last_n_steps[ind] = loss_curr

tol = 2 * self.last_n_steps.std() if k > history_length else 2 * last_n_steps[: k - 1].std()

if loss_curr + tol < loss_next:
    params_next = params_curr


######################################################################
# The efficacy of this new tolerance definition is confirmed by
# reproducing the experiment on QN-SPSA in Fig. 1(b) from Ref [1]. In the
# following figure, we show the performance of the optimizer with the two
# tolerance definitions for a 11-qubit system. The shaded areas are the
# profiles of 25 trials of the experiment. One can confirm the
# past-:math:`N`-step (:math:`N=5` for the plot) standard deviation works
# just as good. With the new choice of the tolerance, for each step, the
# QN-SPSA will only need to execute 2(gradient) + 4(metric tensor) +
# 2(current and the next-step loss) = 8 circuits. In practice, we measure
# a 50% reduction in the step-wise optimization time.
#
# The test is done with the Braket Jobs service, as it is a handy tool to
# scale up experiments systematically. We will show how to do that towards
# the end of the tutorial.
#
# .. figure:: ../demonstrations/qnspsa/qnspsa_new_tol.png
#    :align: center
#    :width: 80%
#


######################################################################
# Similarly, with Braket Jobs, we can also confirm that blocking indeed is
# necessary for this second-order SPSA optimizer, though it does not make
# much difference for SPSA. Here the envelope of the QN-SPSA curves
# without blocking is not plotted since it is too noisy to visualize. SPSA
# is implemented through replacing the metric tensor with an identity
# matrix.
#
# .. figure:: ../demonstrations/qnspsa/qnspsa_blocking.png
#    :align: center
#    :width: 80%
#


######################################################################
# Efficiency improvement
# ----------------------
#
# Let’s do a deep dive on how to further improve the execution efficiency
# of the code. In the code example above, we compute gradient, metric
# tensor, and the loss values through individual calls on the
# ``QNode.__call__()`` function (in this example, ``cost_function()``). In
# a hand-wavy argument, each ``QNode.__call__()`` does the following two
# things: (1) it constructs a tape with the given parameters, and then (2)
# calls ``qml.execute()`` to execute the single tape.
#
# However, in this use case, the better practice is to group the tapes and
# call one ``qml.execute()`` on all the tapes. This practice utilizes the
# batch execution feature from Pennylane, and has a few potential
# advantages. Some simulators provide parallelization support, so that the
# grouped tapes can be executed simutaneously. As an example, utilizing
# the `task
# batching <https://docs.aws.amazon.com/braket/latest/developerguide/braket-batching-tasks.html?tag=local002>`__
# feature from the Braket SV1 simulator, we are able to reduce the
# optimization time by 4X for large circuits. For quantum hardwares,
# sending tapes in batches could also enable further efficiency
# improvement in circuit compilation.
#
# With this rewriting, the complete optimizer class is provided in the
# following cell.
#

import random
import pennylane as qml
from pennylane import numpy as np
from scipy.linalg import sqrtm
import warnings


class QNSPSA:
    """Quantum natural SPSA optimizer. Refer to https://quantum-journal.org/papers/q-2021-10-20-567/
    for a detailed description of the methodology. When disable_metric_tensor
    is set to be True, the metric tensor estimation is disabled, and QNSPSA is
    reduced to be a SPSA optimizer.

    Args:
        stepsize (float): The learn rate.
        regularization (float): Regularitzation term to the Fubini-Study
            metric tensor for numerical stability.
        finite_diff_step (float): step size to compute the finite difference
            gradient and the Fubini-Study metric tensor.
        resamplings (int): The number of samples to average for each parameter
            update.
        blocking (boolean): When set to be True, the optimizer only accepts
            updates that leads to a loss value no larger than the loss value
            before update, plus a tolerance. The tolerance is set with the
            parameter history_length.
        history_length (int): When blocking is True, the tolerance is set to be
            the average of the cost values in the last history_length steps.
        disable_metric_tensor (boolean): When set to be True, the optimizer is
            reduced to be a (1st-order) SPSA optimizer.
        seed (int): Seed for the random sampling.
    """

    def __init__(
        self,
        stepsize=1e-3,
        regularization=1e-3,
        finite_diff_step=1e-2,
        resamplings=1,
        blocking=True,
        history_length=5,
        disable_metric_tensor=False,
        seed=None,
    ):
        self.stepsize = stepsize
        self.reg = regularization
        self.finite_diff_step = finite_diff_step
        self.metric_tensor = None
        self.k = 1
        self.resamplings = resamplings
        self.blocking = blocking
        self.last_n_steps = np.zeros(history_length)
        self.history_length = history_length
        self.disable_metric_tensor = disable_metric_tensor
        random.seed(seed)
        return

    def step(self, cost, params):
        """Update trainable arguments with one step of the optimizer.

        .. warning::
            When blocking is set to be True, use step_and_cost instead, as loss
            measurements are required for the updates for the case.

        Args:
            cost (qml.QNode): the QNode wrapper for the objective function for
            optimization
            params (np.array): Parameter before update.

        Returns:
            np.array: The new variable values after step-wise update.
        """
        if self.blocking:
            warnings.warn(
                "step_and_cost() instead of step() is called when "
                "blocking is turned on, as the step-wise loss value "
                "is required by the algorithm.",
                stacklevel=2,
            )
            return self.step_and_cost(cost, params)[0]

        if self.disable_metric_tensor:
            return self.__step_core_first_order(cost, params)
        return self.__step_core(cost, params)

    def step_and_cost(self, cost, params):
        """Update trainable parameters with one step of the optimizer and return
        the corresponding objective function value after the step.

        Args:
            cost (qml.QNode): the QNode wrapper for the objective function for
                optimization
            params (np.array): Parameter before update.

        Returns:
            tuple[np.array, float]: the updated parameter and the objective
                function output before the step.
        """
        params_next = (
            self.__step_core_first_order(cost, params)
            if self.disable_metric_tensor
            else self.__step_core(cost, params)
        )

        if not self.blocking:
            loss_curr = cost(params)
            return params_next, loss_curr
        params_next, loss_curr = self.__apply_blocking(cost, params, params_next)
        return params_next, loss_curr

    def __step_core(self, cost, params):
        grad_avg = np.zeros(params.shape)
        tensor_avg = np.zeros((params.size, params.size))
        for i in range(self.resamplings):
            grad_tapes, grad_dir = self.__get_spsa_grad_tapes(cost, params)
            metric_tapes, tensor_dirs = self.__get_tensor_tapes(cost, params)
            raw_results = qml.execute(grad_tapes + metric_tapes, cost.device, None)
            grad = self.__post_process_grad(raw_results[:2], grad_dir)
            metric_tensor = self.__post_process_tensor(raw_results[2:], tensor_dirs)
            grad_avg = grad_avg * i / (i + 1) + grad / (i + 1)
            tensor_avg = tensor_avg * i / (i + 1) + metric_tensor / (i + 1)

        self.__update_tensor(tensor_avg)
        return self.__get_next_params(params, grad_avg)

    def __step_core_first_order(self, cost, params):
        grad_avg = np.zeros(params.shape)
        for i in range(self.resamplings):
            grad_tapes, grad_dir = self.__get_spsa_grad_tapes(cost, params)
            raw_results = qml.execute(grad_tapes, cost.device, None)
            grad = self.__post_process_grad(raw_results, grad_dir)
            grad_avg = grad_avg * i / (i + 1) + grad / (i + 1)
        return params - self.stepsize * grad_avg

    def __post_process_grad(self, grad_raw_results, grad_dir):
        loss_forward, loss_backward = grad_raw_results
        grad = (loss_forward - loss_backward) / (2 * self.finite_diff_step) * grad_dir
        return grad

    def __post_process_tensor(self, tensor_raw_results, tensor_dirs):
        tensor_finite_diff = (
            tensor_raw_results[0][0][0]
            - tensor_raw_results[1][0][0]
            - tensor_raw_results[2][0][0]
            + tensor_raw_results[3][0][0]
        )
        metric_tensor = (
            -(
                np.tensordot(tensor_dirs[0], tensor_dirs[1], axes=0)
                + np.tensordot(tensor_dirs[1], tensor_dirs[0], axes=0)
            )
            * tensor_finite_diff
            / (8 * self.finite_diff_step * self.finite_diff_step)
        )
        return metric_tensor

    def __get_next_params(self, params, gradient):
        grad_vec, params_vec = gradient.reshape(-1), params.reshape(-1)
        new_params_vec = np.linalg.solve(
            self.metric_tensor,
            (-self.stepsize * grad_vec + np.matmul(self.metric_tensor, params_vec)),
        )
        return new_params_vec.reshape(params.shape)

    def __get_perturbation_direction(self, params):
        param_number = len(params) if isinstance(params, list) else params.size
        sample_list = random.choices([-1, 1], k=param_number)
        direction = np.array(sample_list).reshape(params.shape)
        return direction

    def __get_spsa_grad_tapes(self, cost, params):
        direction = self.__get_perturbation_direction(params)
        cost.construct([params + self.finite_diff_step * direction], {})
        tape_forward = cost.tape.copy(copy_operations=True)
        cost.construct([params - self.finite_diff_step * direction], {})
        tape_backward = cost.tape.copy(copy_operations=True)
        return [tape_forward, tape_backward], direction

    def __update_tensor(self, tensor_raw):
        tensor_avg = self.__get_tensor_moving_avg(tensor_raw)
        tensor_regularized = self.__regularize_tensor(tensor_avg)
        self.metric_tensor = tensor_regularized
        self.k += 1

    def __get_tensor_tapes(self, cost, params):
        dir1 = self.__get_perturbation_direction(params)
        dir2 = self.__get_perturbation_direction(params)
        perturb1 = dir1 * self.finite_diff_step
        perturb2 = dir2 * self.finite_diff_step
        dir_vecs = dir1.reshape(-1), dir2.reshape(-1)

        tapes = [
            self.__get_overlap_tape(cost, params, params + perturb1 + perturb2),
            self.__get_overlap_tape(cost, params, params + perturb1),
            self.__get_overlap_tape(cost, params, params - perturb1 + perturb2),
            self.__get_overlap_tape(cost, params, params - perturb1),
        ]
        return tapes, dir_vecs

    def __get_overlap_tape(self, cost, params1, params2):
        op_forward = self.__get_operations(cost, params1)
        op_inv = self.__get_operations(cost, params2)

        with qml.tape.QuantumTape() as tape:
            for op in op_forward:
                qml.apply(op)
            for op in reversed(op_inv):
                op.adjoint()
            qml.probs(wires=cost.tape.wires.labels)
        return tape

    def __get_operations(self, cost, params):
        cost.construct([params], {})
        return cost.tape.operations

    def __get_tensor_moving_avg(self, metric_tensor):
        if self.metric_tensor is None:
            self.metric_tensor = np.identity(metric_tensor.shape[0])
        return self.k / (self.k + 1) * self.metric_tensor + 1 / (self.k + 1) * metric_tensor

    def __regularize_tensor(self, metric_tensor):
        tensor_reg = np.real(sqrtm(np.matmul(metric_tensor, metric_tensor)))
        return (tensor_reg + self.reg * np.identity(metric_tensor.shape[0])) / (1 + self.reg)

    def __apply_blocking(self, cost, params_curr, params_next):
        cost.construct([params_curr], {})
        tape_loss_curr = cost.tape.copy(copy_operations=True)
        cost.construct([params_next], {})
        tape_loss_next = cost.tape.copy(copy_operations=True)

        loss_curr, loss_next = qml.execute([tape_loss_curr, tape_loss_next], cost.device, None)
        # self.k has been updated earlier
        ind = (self.k - 2) % self.history_length
        self.last_n_steps[ind] = loss_curr

        tol = (
            2 * self.last_n_steps.std()
            if self.k > self.history_length
            else 2 * self.last_n_steps[: self.k - 1].std()
        )

        if loss_curr + tol < loss_next:
            params_next = params_curr
        return params_next, loss_curr


######################################################################
# Let’s see how it performs on our QAOA example:
#

opt = QNSPSA(stepsize=5e-2)
params_init = 2 * np.pi * (np.random.rand(2, depth) - 0.5)
params = params_init
for i in range(300):
    params, loss = opt.step_and_cost(cost_function, params)
    if i % 40 == 0:
        print(f"Step {i}: cost = {loss:.4f}")


######################################################################
# The optimizer performs reasonably well: the loss drops over optimization
# steps and converges finally. We then reproduce the benchmarking test
# between the gradient descent, quantum natural gradient descent, SPSA and
# QN-SPSA in Fig. 1(b) of Ref [1] with the following Braket Job (find a
# more detailed version of the example and the corresponding scripts
# `here <https://github.com/aws/amazon-braket-examples/blob/qnspsa/examples/hybrid_jobs/6_QNSPSA_optimizer_with_embedded_simulator/qnspsa_with_embedded_simulator.ipynb>`__
# [TODO: change to the main branch link]).
#

from braket.aws import AwsSession, AwsQuantumJob
from braket.jobs.config import InstanceConfig
from braket.jobs.image_uris import Framework, retrieve_image
import boto3

region_name = AwsSession().region
image_uri = retrieve_image(Framework.BASE, region_name)

n_qubits = 11

hyperparameters = {
    "n_qubits": n_qubits,
    "n_layers": 4,
    "shots": 8192,
    "max_iter": 600,
    "learn_rate": 1e-2,
    "spsa_repeats": 25,
}

job_name = f"ref-paper-benchmark-qubit-{n_qubits}"
instance_config = InstanceConfig(instanceType="ml.m5.large", volumeSizeInGb=30, instanceCount=1)

job = AwsQuantumJob.create(
    device="local:pennylane/lightning.qubit",
    source_module="source_scripts",
    entry_point="source_scripts.benchmark_ref_paper_converge_speed",
    job_name=job_name,
    hyperparameters=hyperparameters,
    instance_config=instance_config,
    image_uri=image_uri,
    wait_until_complete=False,
)


######################################################################
# Visualizing the Job results, we get the following plot. In the plot, the
# observations from Gacon et al. [1] are reproduced. This confirms our
# implementation of the optimizer. In this example, the average behavior
# of SPSA matches the one from GD. QN-SPSA outperforms the two both in the
# final loss value and in the step-wise convergence speed. Step-wise
# speaking, QNG performs the best among the 4 candidates.
#
# We also want to take the optimization time into consideration. The
# step-wise optimization times for GD, QNG, SPSA and QN-SPSA are 0.43s,
# 0.75s, 0.03s and 0.20s. One can see the stochastic optimizers are
# significantly faster, and this advantage will become more prominent with
# larger and more complicated circuits due to the :math:`O(1)` to
# :math:`O(N)` scaling advantage. On the other hand, although QN-SPSA is
# slower comparing to SPSA, the difference does not scale with the system
# size. Overall, QN-SPSA shows up as a very promising candidate for
# complicated VQE problems.
#
# .. figure:: ../demonstrations/qnspsa/qnspsa_braket.png
#    :align: center
#    :width: 80%


######################################################################
# To sum up, in this tutorial, we showed step-by-step how we can implement
# the QN-SPSA optimizer with Pennylane, along with a few tricks to further
# improve the optimizer’s performance. We also demonstrated how one can
# scale up the benchmarking experiments with Braket Jobs.
#


######################################################################
# References
# ----------
#
# [1] Gacon, J., Zoufal, C., Carleo, G., & Woerner, S. (2021).
# *Simultaneous perturbation stochastic approximation of the quantum
# fisher information*. Quantum, 5, 567.
#
# [2] Simultaneous perturbation stochastic approximation (2022).
# Wikipedia.
# https://en.wikipedia.org/wiki/Simultaneous_perturbation_stochastic_approximation
#
# [3] Fubini–Study metric (2022). Wikipedia.
# https://en.wikipedia.org/wiki/Fubini%E2%80%93Study_metric
#
# [4] Stokes, J., Izaac, J., Killoran, N., & Carleo, G. (2020). *Quantum
# natural gradient*. Quantum, 4, 269.
#
# [5] Yamamoto, N. (2019). *On the natural gradient for variational
# quantum eigensolver*. arXiv preprint arXiv:1909.05074.
#
# [6] Spall, J. C. (1997). *Accelerated second-order stochastic
# optimization using only function measurements*. In Proceedings of the
# 36th IEEE Conference on Decision and Control (Vol. 2, pp. 1417-1424).
# IEEE.
#
