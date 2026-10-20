# AI usage

AI assistance was used openly in this project. The assignment explicitly permits
it and asks the candidate to remain responsible for the resulting system.

Codex helped extract the supplied assignment, compare possible product ideas,
refine requirements and choose a small first iteration. The candidate chose a
personal job application tracker, Python/FastAPI, Swagger as the interface, and
local single-user operation without login.

Implementation work was divided between a backend agent, a test agent and a
delivery/documentation agent. They received the same SRS and separate file
ownership. An integrating agent owns the contract, dependency configuration,
review of the combined result, verification and final documentation. Tests are
derived from the requirements rather than supplied by the backend author alone.

AI provided the most value in turning an open-ended assignment into explicit
boundaries, identifying edge cases around partial updates and follow-up dates,
and checking agreement between requirements, code and delivery instructions.
Official FastAPI and SQLAlchemy documentation was consulted for session
lifecycle, test dependencies, foreign keys and UTC timestamp handling.

Code and documentation are AI-assisted; they are not represented as unaided
manual work. The style goal is ordinary, readable Python: direct domain names,
small functions, a consistent layout and comments that explain decisions. No
artificial mistakes or reconstructed commit dates are used to imitate authorship.

The validation report distinguishes performed checks from deferred work. Passing
tests does not validate the product hypothesis or prove readiness for public
hosting. Before presenting this work, the candidate should be able to explain
the API contract, transaction boundary, date rules, SQLite limitations and the
tests that protect them.
