//! vrpq_stark — real transparent STARK (winterfell) for VeRedact-PQ's PQZK policy relation, callable
//! from Python in-process (PyO3), so no subprocess cost lands inside a timed region.
//!
//! Python API:
//!   Registry(credentials: list[(secret:int, requester:int)])  .root() -> (int, int)   .path(index) -> bytes
//!   prove(secret, requester, index, path_bytes, statement: (int,int), queries, blowup, grinding) -> bytes
//!   verify(proof, root: (int,int), requester, statement: (int,int), queries, blowup, grinding) -> bool
//!   rescue_leaf(secret, requester) -> (int, int)
//! Field: f128 (winterfell); vector commitments: SHA3-256 (post-quantum hash, as in the manuscript).

mod helpers;
mod policy_air;
mod rescue;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use winterfell::{
    crypto::{hashers::Sha3_256, DefaultRandomCoin, MerkleTree, VectorCommitment},
    math::{fields::f128::BaseElement, StarkField},
    AcceptableOptions, BatchingMethod, FieldExtension, Proof, ProofOptions, Prover,
};

use policy_air::{PolicyAir, PolicyProver, PublicInputs};
use rescue::{Hash, Rescue128};

type H = Sha3_256<BaseElement>;

fn el(x: u128) -> BaseElement {
    BaseElement::new(x)
}

fn options(queries: usize, blowup: usize, grinding: u32) -> ProofOptions {
    ProofOptions::new(queries, blowup, grinding, FieldExtension::Quadratic, 8, 31,
                      BatchingMethod::Linear, BatchingMethod::Linear)
}

#[pyfunction]
fn rescue_leaf(secret: u128, requester: u128) -> (u128, u128) {
    let h = Rescue128::digest(&[el(secret), el(requester)]).to_elements();
    (h[0].as_int(), h[1].as_int())
}

/// Credential registry: Rescue-Prime Merkle tree over Rescue(secret, requester) leaves.
#[pyclass]
struct Registry {
    tree: MerkleTree<Rescue128>,
}

#[pymethods]
impl Registry {
    #[new]
    fn new(credentials: Vec<(u128, u128)>) -> PyResult<Self> {
        // The AIR spends one 8-step Rescue cycle per tree level plus one for the leaf, and the trace
        // length must be a power of two, so (depth + 1) must be a power of two: depth 7, 15, 31, ...
        let n = credentials.len();
        let depth = n.trailing_zeros() as usize;
        if !n.is_power_of_two() || n < 2 || !(depth + 1).is_power_of_two() {
            return Err(PyValueError::new_err(
                "registry size must be 2^depth with depth + 1 a power of two (2^7, 2^15, 2^31)"));
        }
        let leaves: Vec<Hash> = credentials.iter().map(|(s, r)| Rescue128::digest(&[el(*s), el(*r)])).collect();
        let tree = MerkleTree::new(leaves).map_err(|e| PyValueError::new_err(format!("{e:?}")))?;
        Ok(Registry { tree })
    }

    fn root(&self) -> (u128, u128) {
        let r = self.tree.commitment().to_elements();
        (r[0].as_int(), r[1].as_int())
    }

    /// Authentication path for `index`, serialised as consecutive (u128, u128) little-endian pairs
    /// starting with the leaf hash.
    fn path<'py>(&self, py: Python<'py>, index: usize) -> PyResult<Bound<'py, PyBytes>> {
        let (leaf, path) = self.tree.open(index).map_err(|e| PyValueError::new_err(format!("{e:?}")))?;
        let mut out = Vec::new();
        for h in std::iter::once(leaf).chain(path.into_iter()) {
            for e in h.to_elements() {
                out.extend_from_slice(&e.as_int().to_le_bytes());
            }
        }
        Ok(PyBytes::new(py, &out))
    }
}

fn decode_path(bytes: &[u8]) -> PyResult<Vec<Hash>> {
    if bytes.len() % 32 != 0 {
        return Err(PyValueError::new_err("path length must be a multiple of 32"));
    }
    Ok(bytes
        .chunks(32)
        .map(|c| {
            let a = u128::from_le_bytes(c[..16].try_into().unwrap());
            let b = u128::from_le_bytes(c[16..].try_into().unwrap());
            Hash::new(el(a), el(b))
        })
        .collect())
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn prove<'py>(
    py: Python<'py>, secret: u128, requester: u128, index: usize, path: &[u8], root: (u128, u128),
    statement: (u128, u128), queries: usize, blowup: usize, grinding: u32,
) -> PyResult<Bound<'py, PyBytes>> {
    let branch = decode_path(path)?;
    let pub_inputs = PublicInputs {
        registry_root: [el(root.0), el(root.1)],
        requester: el(requester),
        statement: [el(statement.0), el(statement.1)],
    };
    let prover = PolicyProver::<H>::new(options(queries, blowup, grinding), pub_inputs);
    let trace = prover.build_trace([el(secret), el(requester)], &branch, index);
    let proof = py
        .allow_threads(|| prover.prove(trace))
        .map_err(|e| PyValueError::new_err(format!("prover: {e:?}")))?;
    Ok(PyBytes::new(py, &proof.to_bytes()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn verify(py: Python<'_>, proof: &[u8], root: (u128, u128), requester: u128, statement: (u128, u128),
          queries: usize, blowup: usize, grinding: u32) -> bool {
    let Ok(proof) = Proof::from_bytes(proof) else { return false };
    let pub_inputs = PublicInputs {
        registry_root: [el(root.0), el(root.1)],
        requester: el(requester),
        statement: [el(statement.0), el(statement.1)],
    };
    let acceptable = AcceptableOptions::OptionSet(vec![options(queries, blowup, grinding)]);
    py.allow_threads(|| {
        winterfell::verify::<PolicyAir, H, DefaultRandomCoin<H>, MerkleTree<H>>(proof, pub_inputs, &acceptable).is_ok()
    })
}

#[pymodule]
fn vrpq_stark(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Registry>()?;
    m.add_function(wrap_pyfunction!(rescue_leaf, m)?)?;
    m.add_function(wrap_pyfunction!(prove, m)?)?;
    m.add_function(wrap_pyfunction!(verify, m)?)?;
    Ok(())
}
