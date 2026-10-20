**Subject:** Issuer 03 cards declined on all top-ups since 25 Aug, 09:40 (evidence attached)

Hi team,

Since **25 August, between 08:43 and 10:30**, every card top-up with an **Issuer 03** card has been declined.

**What we see**
- **0 of 3,888** Issuer 03 attempts accepted since then. Before 25 Aug, 85% were accepted.
- It happens on **all three** of our payment gateways, and each gateway returns a different reason: "invalid merchant", "declined at 3DS start", "blocked by the bank".
- The same gateways accept **82%** of cards from every other issuer over the same period, which is normal.
- Every amount is affected (including top-ups under $20), as are both card brands, both card currencies, and old and new accounts alike.

**What this points to**
A change on the issuer's side on the morning of 25 August. The most likely candidates are a block on our merchant category, or a 3-D Secure configuration change for our merchant ID.

**Impact so far**
- 831 customers affected, averaging 4.7 attempts each
- about $231K of top-ups not completed, or roughly $4.8K a day

**What we need from you**
Please check for any rule or 3DS change applied to our merchant IDs on 25 Aug, and tell us when it can be reverted. We can share attempt IDs and timestamps for any sample you need.

Thanks,
Jamil Saleh
Operations & Data Reporting
