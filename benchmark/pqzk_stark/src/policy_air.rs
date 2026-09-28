// VeRedact-PQ PQZK policy relation (Phase 3 Step 4) as a winterfell AIR.
//
// Adapted from winterfell v0.13.1 examples/src/merkle/{air,prover}.rs (MIT License, Copyright (c)
// Facebook, Inc. and its affiliates). Changes: public inputs carry the requester identity and the
// digest of the Phase-3 statement x_i, and an assertion binds the credential leaf to the requester.
//
// Relation proven (witness: credential secret, leaf index, authentication path):
//   ValidCred      : Rescue(secret, requester) is a leaf of the credential registry whose root is
//                    committed in the policy commitment C_P
//   RequesterBound : the leaf's second element equals the public requester identity
//   statement bind : digest(x_i) is part of the public inputs and therefore of the Fiat-Shamir
//                    transcript, so the proof cannot be replayed for another request/state
// Not encoded (documented deviation): attribute predicates of PrivatePolicy beyond membership.

use winterfell::{
    math::{fields::f128::BaseElement, FieldElement, ToElements},
    matrix::ColMatrix,
    Air, AirContext, Assertion, AuxRandElements, CompositionPoly, CompositionPolyTrace,
    ConstraintCompositionCoefficients, DefaultConstraintCommitment, DefaultConstraintEvaluator,
    DefaultTraceLde, EvaluationFrame, PartitionOptions, ProofOptions, Prover, StarkDomain,
    TraceInfo, TracePolyTable, TraceTable, TransitionConstraintDegree,
    crypto::{DefaultRandomCoin, ElementHasher, MerkleTree},
};
use core::marker::PhantomData;

use crate::helpers::{are_equal, is_binary, is_zero, not, EvaluationResult};
use crate::rescue::{self, CYCLE_LENGTH as HASH_CYCLE_LEN, NUM_ROUNDS, STATE_WIDTH as HASH_STATE_WIDTH};

pub const TRACE_WIDTH: usize = 7;

#[derive(Clone)]
pub struct PublicInputs {
    pub registry_root: [BaseElement; 2],
    pub requester: BaseElement,
    pub statement: [BaseElement; 2],
}

impl ToElements<BaseElement> for PublicInputs {
    fn to_elements(&self) -> Vec<BaseElement> {
        vec![self.registry_root[0], self.registry_root[1], self.requester, self.statement[0], self.statement[1]]
    }
}

pub struct PolicyAir {
    context: AirContext<BaseElement>,
    pub_inputs: PublicInputs,
}

impl Air for PolicyAir {
    type BaseField = BaseElement;
    type PublicInputs = PublicInputs;

    fn new(trace_info: TraceInfo, pub_inputs: PublicInputs, options: ProofOptions) -> Self {
        let mut degrees = vec![TransitionConstraintDegree::with_cycles(5, vec![HASH_CYCLE_LEN]); 6];
        degrees.push(TransitionConstraintDegree::new(2));
        assert_eq!(TRACE_WIDTH, trace_info.width());
        PolicyAir { context: AirContext::new(trace_info, degrees, 5, options), pub_inputs }
    }

    fn context(&self) -> &AirContext<Self::BaseField> {
        &self.context
    }

    fn evaluate_transition<E: FieldElement + From<Self::BaseField>>(
        &self,
        frame: &EvaluationFrame<E>,
        periodic_values: &[E],
        result: &mut [E],
    ) {
        let current = frame.current();
        let next = frame.next();
        let hash_flag = periodic_values[0];
        let ark = &periodic_values[1..];
        rescue::enforce_round(result, &current[..HASH_STATE_WIDTH], &next[..HASH_STATE_WIDTH], ark, hash_flag);

        let hash_init_flag = not(hash_flag);
        let bit = next[6];
        let not_bit = not(bit);
        result.agg_constraint(0, hash_init_flag, not_bit * are_equal(current[0], next[0]));
        result.agg_constraint(1, hash_init_flag, not_bit * are_equal(current[1], next[1]));
        result.agg_constraint(2, hash_init_flag, bit * are_equal(current[0], next[2]));
        result.agg_constraint(3, hash_init_flag, bit * are_equal(current[1], next[3]));
        result.agg_constraint(4, hash_init_flag, is_zero(next[4]));
        result.agg_constraint(5, hash_init_flag, is_zero(next[5]));
        result[6] = is_binary(current[6]);
    }

    fn get_assertions(&self) -> Vec<Assertion<Self::BaseField>> {
        let last_step = self.trace_length() - 1;
        vec![
            Assertion::single(1, 0, self.pub_inputs.requester), // RequesterBound
            Assertion::single(0, last_step, self.pub_inputs.registry_root[0]),
            Assertion::single(1, last_step, self.pub_inputs.registry_root[1]),
            Assertion::periodic(4, 0, HASH_CYCLE_LEN, BaseElement::ZERO),
            Assertion::periodic(5, 0, HASH_CYCLE_LEN, BaseElement::ZERO),
        ]
    }

    fn get_periodic_column_values(&self) -> Vec<Vec<Self::BaseField>> {
        let mut mask = vec![BaseElement::ONE; HASH_CYCLE_LEN];
        mask[HASH_CYCLE_LEN - 1] = BaseElement::ZERO;
        let mut result = vec![mask];
        result.append(&mut rescue::get_round_constants());
        result
    }
}

pub struct PolicyProver<H: ElementHasher> {
    options: ProofOptions,
    pub_inputs: PublicInputs,
    _hasher: PhantomData<H>,
}

impl<H: ElementHasher> PolicyProver<H> {
    pub fn new(options: ProofOptions, pub_inputs: PublicInputs) -> Self {
        Self { options, pub_inputs, _hasher: PhantomData }
    }

    /// value = [credential secret, requester id]; branch[0] = leaf hash, branch[1..] = path.
    pub fn build_trace(&self, value: [BaseElement; 2], branch: &[rescue::Hash], index: usize) -> TraceTable<BaseElement> {
        let trace_length = branch.len() * HASH_CYCLE_LEN;
        let mut trace = TraceTable::new(TRACE_WIDTH, trace_length);
        let branch = &branch[1..];
        trace.fill(
            |state| {
                state[0] = value[0];
                state[1] = value[1];
                state[2..].fill(BaseElement::ZERO);
            },
            |step, state| {
                let cycle_num = step / HASH_CYCLE_LEN;
                let cycle_pos = step % HASH_CYCLE_LEN;
                if cycle_pos < NUM_ROUNDS {
                    rescue::apply_round(&mut state[..HASH_STATE_WIDTH], step);
                } else {
                    let node = branch[cycle_num].to_elements();
                    let bit = BaseElement::new(((index >> cycle_num) & 1) as u128);
                    if bit == BaseElement::ZERO {
                        state[2] = node[0];
                        state[3] = node[1];
                    } else {
                        state[2] = state[0];
                        state[3] = state[1];
                        state[0] = node[0];
                        state[1] = node[1];
                    }
                    state[4] = BaseElement::ZERO;
                    state[5] = BaseElement::ZERO;
                    state[6] = bit;
                }
            },
        );
        trace.set(6, 1, FieldElement::ONE); // as in the upstream example: keeps the bit column degree stable
        trace
    }
}

impl<H: ElementHasher> Prover for PolicyProver<H>
where
    H: ElementHasher<BaseField = BaseElement> + Sync,
{
    type BaseField = BaseElement;
    type Air = PolicyAir;
    type Trace = TraceTable<BaseElement>;
    type HashFn = H;
    type VC = MerkleTree<H>;
    type RandomCoin = DefaultRandomCoin<Self::HashFn>;
    type TraceLde<E: FieldElement<BaseField = Self::BaseField>> = DefaultTraceLde<E, Self::HashFn, Self::VC>;
    type ConstraintCommitment<E: FieldElement<BaseField = Self::BaseField>> = DefaultConstraintCommitment<E, H, Self::VC>;
    type ConstraintEvaluator<'a, E: FieldElement<BaseField = Self::BaseField>> = DefaultConstraintEvaluator<'a, Self::Air, E>;

    fn get_pub_inputs(&self, _trace: &Self::Trace) -> PublicInputs {
        self.pub_inputs.clone()
    }

    fn options(&self) -> &ProofOptions {
        &self.options
    }

    fn new_trace_lde<E: FieldElement<BaseField = Self::BaseField>>(
        &self,
        trace_info: &TraceInfo,
        main_trace: &ColMatrix<Self::BaseField>,
        domain: &StarkDomain<Self::BaseField>,
        partition_option: PartitionOptions,
    ) -> (Self::TraceLde<E>, TracePolyTable<E>) {
        DefaultTraceLde::new(trace_info, main_trace, domain, partition_option)
    }

    fn new_evaluator<'a, E: FieldElement<BaseField = Self::BaseField>>(
        &self,
        air: &'a Self::Air,
        aux_rand_elements: Option<AuxRandElements<E>>,
        composition_coefficients: ConstraintCompositionCoefficients<E>,
    ) -> Self::ConstraintEvaluator<'a, E> {
        DefaultConstraintEvaluator::new(air, aux_rand_elements, composition_coefficients)
    }

    fn build_constraint_commitment<E: FieldElement<BaseField = Self::BaseField>>(
        &self,
        composition_poly_trace: CompositionPolyTrace<E>,
        num_constraint_composition_columns: usize,
        domain: &StarkDomain<Self::BaseField>,
        partition_options: PartitionOptions,
    ) -> (Self::ConstraintCommitment<E>, CompositionPoly<E>) {
        DefaultConstraintCommitment::new(composition_poly_trace, num_constraint_composition_columns, domain, partition_options)
    }
}
