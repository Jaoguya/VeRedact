// Constraint helpers copied from winterfell v0.13.1 examples/src/utils/mod.rs (MIT License,
// Copyright (c) Facebook, Inc. and its affiliates); printing helpers omitted.
use winterfell::{
    math::FieldElement,

};



// CONSTRAINT EVALUATION HELPERS
// ================================================================================================

/// Returns zero only when a == b.
pub fn are_equal<E: FieldElement>(a: E, b: E) -> E {
    a - b
}

/// Returns zero only when a == zero.
pub fn is_zero<E: FieldElement>(a: E) -> E {
    a
}

/// Returns zero only when a = zero || a == one.
pub fn is_binary<E: FieldElement>(a: E) -> E {
    a * a - a
}

/// Return zero when a == one, and one when a == zero;
/// assumes that a is a binary value.
pub fn not<E: FieldElement>(a: E) -> E {
    E::ONE - a
}

// TRAIT TO SIMPLIFY CONSTRAINT AGGREGATION
// ================================================================================================

pub trait EvaluationResult<E> {
    fn agg_constraint(&mut self, index: usize, flag: E, value: E);
}

impl<E: FieldElement> EvaluationResult<E> for [E] {
    fn agg_constraint(&mut self, index: usize, flag: E, value: E) {
        self[index] += flag * value;
    }
}

impl<E: FieldElement> EvaluationResult<E> for Vec<E> {
    fn agg_constraint(&mut self, index: usize, flag: E, value: E) {
        self[index] += flag * value;
    }
}

