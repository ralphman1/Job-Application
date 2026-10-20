# Problem definition

A job seeker can have several applications moving at different speeds. Statuses,
recruiter messages and promises to follow up tend to be scattered across email,
notes and spreadsheets. Remembering the next action becomes harder as the search
continues.

The first iteration is a local application tracker for one person. It keeps the
current status, status history and one dated next action per application. Its
main outcome is a useful queue: what needs attention today, including overdue
work? The user interacts through an HTTP API and its Swagger documentation.

## User and value hypothesis

The intended user is a technically comfortable job seeker who can use Swagger or
an HTTP client. A single place for dated actions may reduce missed follow-ups.
This is a hypothesis, not a result of user research. The next product validation
step is to ask a job seeker to track real applications for a week and observe
whether the action queue is useful. API usability is a deliberate limitation of
this iteration.

## First iteration

Record applications already submitted, update their details and stage, inspect
their status history, and find active next actions due by a chosen date. Search,
filtering and counts provide context without building a separate dashboard.

An application can be added at its current stage, so an existing job search can
be entered without pretending every application was just submitted. Separate
applications at the same company and position are valid.

## Non-goals

- Accounts, authentication, multiple users and public hosting.
- A frontend, vacancy discovery, scraping or job board integrations.
- Email reminders, background jobs, CV uploads and calendar integration.
- Separate recruiter, company or interview management.

This project addresses a candidate-selected problem for the SpheraX Software
Engineer Technical Assignment. The supplied assignment describes the engineering
process and deliverables; it does not prescribe this product or technology stack.
