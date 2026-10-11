# Security reporting and supported scope

Report suspected defects privately to the repository owner through GitHub contact
options before publishing a reproducer affecting deployed users. No private
vulnerability-reporting feature or monitored email is assumed available.

The supported boundary is untrusted VeriMorph text under a trusted Python host.
No OS sandbox exists. Do not run untrusted Python plugins or the historical
prototype as if they were isolated. See THREAT_MODEL.md for exact limitations.

Experimental version 0.1.0 is the only implementation in this repository.
There are no compatibility or long-term support promises.
