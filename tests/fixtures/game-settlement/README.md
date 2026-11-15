# Game completion and rewards

Players submit a completion to the Python API after the external TypeScript
verifier has checked a game. The verifier is represented by documented intent
only; its implementation and runtime guarantees are outside this fixture.
The completion handler asks settlement to check eligibility and credit a wallet.
Wallet failures are surfaced. Purchasing cosmetics is independently invocable;
there is no required reward-to-purchase ordering. Duplicate completion handling
and cross-service atomicity remain unverified.
