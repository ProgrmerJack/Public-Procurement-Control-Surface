# Contributing

Thank you for your interest in contributing to this research project!

## Repository

**GitHub:** [ProgrmerJack/Public-Procurement-Control-Surface](https://github.com/ProgrmerJack/Public-Procurement-Control-Surface)

**Citation:** Ashuraliyev, A. (2026). Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement. *Nature Sustainability*.

## Ways to Contribute

### 1. Report Issues

- Bug reports
- Data quality issues
- Documentation improvements
- Methodological suggestions

Please open an issue at: https://github.com/ProgrmerJack/Public-Procurement-Control-Surface/issues

### 2. Data Contributions

We welcome contributions adding new OCDS-compliant procurement data sources:

1. Fork the repository
2. Add a new downloader in `scripts/lib/data_acquisition.py`
3. Add harmonization logic in `scripts/lib/`
4. Add tests in `tests/` (import from `scripts.lib.*`)
5. Update `config/countries.yaml`
6. Submit a pull request

### 3. Methodological Improvements

- Alternative causal estimators
- Additional robustness checks
- Enhanced carbon intensity mappings
- Cross-validation methods

### 4. Documentation

- Clarify existing documentation
- Add examples
- Improve reproducibility guides

## Development Setup

```bash
# Fork and clone
git clone https://github.com/ProgrmerJack/Public-Procurement-Control-Surface.git
cd Public-Procurement-Control-Surface

# Create environment
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt

# Build and verify the Data Descriptor
python scripts/descriptor/build_partA_panel.py
python scripts/descriptor/verify_claims.py

# Run tests
pytest tests/
```

## Code Style

- Python: Follow PEP 8
- Use type hints
- Write docstrings (Google style)
- Add tests for new functionality

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and add tests
3. Run `pytest tests/` and ensure all pass
4. Update documentation if needed
5. Submit PR with clear description

## Code of Conduct

Be respectful and constructive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

## Contact

**Abduxoliq Ashuraliyev**  
Email: jack00040008@outlook.com  
ORCID: [0009-0003-5482-5526](https://orcid.org/0009-0003-5482-5526)

## License

By contributing, you agree that your contributions will be licensed under MIT (code) and CC-BY-4.0 (data).
