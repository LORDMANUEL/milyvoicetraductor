//! MilyVoice 3 component supervisor foundation.
//!
//! Foundation v1 owns component identity, lifecycle and manifest validation.
//! It intentionally has no runtime dependencies so it can evolve independently
//! from the MilyVoice 2.1.x workspace.

use std::collections::HashSet;
use std::error::Error;
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ComponentStage {
    Experimental,
    Development,
    Candidate,
    Certified,
    Frozen,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ComponentDescriptor {
    pub id: String,
    pub version: String,
    pub contract: String,
    pub stage: ComponentStage,
    pub required: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProductDescriptor {
    pub name: String,
    pub version: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProductManifest {
    pub product: ProductDescriptor,
    pub components: Vec<ComponentDescriptor>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ManifestError {
    EmptyProductName,
    EmptyProductVersion,
    EmptyComponents,
    DuplicateComponentId(String),
    InvalidComponentId(String),
    InvalidComponentVersion { id: String, version: String },
    InvalidContract { id: String, contract: String },
}

impl fmt::Display for ManifestError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptyProductName => formatter.write_str("product name must not be empty"),
            Self::EmptyProductVersion => formatter.write_str("product version must not be empty"),
            Self::EmptyComponents => formatter.write_str("manifest must contain at least one component"),
            Self::DuplicateComponentId(id) => write!(formatter, "duplicate component id: {id}"),
            Self::InvalidComponentId(id) => write!(formatter, "invalid component id: {id}"),
            Self::InvalidComponentVersion { id, version } => {
                write!(formatter, "invalid component version for {id}: {version}")
            }
            Self::InvalidContract { id, contract } => {
                write!(formatter, "invalid contract for {id}: {contract}")
            }
        }
    }
}

impl Error for ManifestError {}

impl ProductManifest {
    pub fn validate(&self) -> Result<(), ManifestError> {
        if self.product.name.trim().is_empty() {
            return Err(ManifestError::EmptyProductName);
        }
        if self.product.version.trim().is_empty() {
            return Err(ManifestError::EmptyProductVersion);
        }
        if self.components.is_empty() {
            return Err(ManifestError::EmptyComponents);
        }

        let mut ids = HashSet::with_capacity(self.components.len());
        for component in &self.components {
            if !is_valid_name(&component.id) {
                return Err(ManifestError::InvalidComponentId(component.id.clone()));
            }
            if !is_release_version(&component.version) {
                return Err(ManifestError::InvalidComponentVersion {
                    id: component.id.clone(),
                    version: component.version.clone(),
                });
            }
            if !is_contract_id(&component.contract) {
                return Err(ManifestError::InvalidContract {
                    id: component.id.clone(),
                    contract: component.contract.clone(),
                });
            }
            if !ids.insert(component.id.clone()) {
                return Err(ManifestError::DuplicateComponentId(component.id.clone()));
            }
        }

        Ok(())
    }
}

fn is_valid_name(value: &str) -> bool {
    let mut chars = value.chars();
    let Some(first) = chars.next() else {
        return false;
    };
    if !first.is_ascii_lowercase() {
        return false;
    }

    let mut previous_hyphen = false;
    for character in chars {
        match character {
            'a'..='z' | '0'..='9' => previous_hyphen = false,
            '-' if !previous_hyphen => previous_hyphen = true,
            _ => return false,
        }
    }

    !previous_hyphen
}

fn is_release_version(value: &str) -> bool {
    let mut parts = value.split('.');
    let first = parts.next();
    let second = parts.next();
    let third = parts.next();
    if parts.next().is_some() {
        return false;
    }

    [first, second, third].into_iter().all(|part| {
        part.is_some_and(|field| !field.is_empty() && field.chars().all(|c| c.is_ascii_digit()))
    })
}

fn is_contract_id(value: &str) -> bool {
    let mut segments = value.split('/');
    let Some(name) = segments.next() else {
        return false;
    };
    let Some(version) = segments.next() else {
        return false;
    };
    if segments.next().is_some() || !is_valid_name(name) {
        return false;
    }

    let Some(major) = version.strip_prefix('v') else {
        return false;
    };
    if major.is_empty() || !major.chars().all(|c| c.is_ascii_digit()) {
        return false;
    }

    major.parse::<u64>().is_ok_and(|value| value > 0)
}
