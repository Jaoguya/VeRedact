# Efficient Auditing and Querying in Verifiable Redactable Blockchain A Lightweight VDS Protocol with Integrity Verificat

> Full text extracted from `Efficient_Auditing_and_Querying_in_Verifiable_Redactable_Blockchain_A_Lightweight_VDS_Protocol_with_Integrity_Verificat.pdf` with `pdftotext`. Equations, tables and figures embedded as images or complex layout may be garbled or missing; check the PDF for those.

Efficient Auditing and Querying in Verifiable Redactable Blockchain: A Lightweight VDS Protocol with Integrity Verification Xiaoxu Zhang1,2,3 , Zhipeng Cai1,2,3 , Keyan Chen1,2,3 , Guanxiong Ha1,2,3 , Chunfu Jia1,2,3,* 1

The College of Cryptology and Cyber Science, Nankai University, Tianjin, 300350, China. Tianjin Key Laboratory of Network and Data Security Technology, Tianjin, 300350, China. 3 Key Laboratory of Data and Intelligent System Security (DISSec), Tianjin, 300350, China.

2

Abstract—Driven by legal and service demands, redactable blockchains (RBC) have been proposed to balance the editability and immutability of blockchain technology. However, RBC may allow the same block to have multiple valid versions, which malicious nodes could exploit to deceive lightweight nodes, thereby compromising the consistency and integrity of the ledger. To address this issue, we propose an efficient auditing and querying scheme for verifiable redactable blockchain (EAQ-VRBC). It is an auditable verifiable data streaming (VDS) protocol that establishes the RSA accumulator-based revocation mechanism to invalidate outdated blocks in RBC. The trusted node maintains a revocation list stored in a dynamic RSA accumulator. The validity of new blocks is verified by non-membership proofs, ensuring that only the latest data version is considered valid, effectively preventing old data version deception. Compared with existing auditable VDS protocols tailored for RBC, the verification cost of EAQ-VRBC in the query and audit phases is reduced by approximately one order of magnitude. Additionally, EAQVRBC uses identity-based RSA signature auditing to ensure data integrity. Finally, security analysis and performance evaluation confirm the feasibility and efficiency of the proposed solution. Index Terms—Verifiable redactable blockchain, Data auditing, RSA accumulator, Chameleon hash function, Verifiable data streaming.

## I. Introduction

With its unique features such as decentralization and immutability, blockchain technology has shown great potential in fields like finance, supply chain, and data sharing [1]– [4]. However, immutability also introduces critical challenges, particularly in privacy protection. For instance, the inability to remove illegal or outdated data conflicts with regulations such as the GDPR’s “right to be forgotten” [5]. Balancing data security, compliance, and privacy thus remains a key challenge for blockchain development. To address this issue, Ateniese et al. [6] proposed Redactable Blockchain (RBC), which leverages chameleon hashing to enable controlled modifications under specific conditions. While RBC enhances flexibility, it raises new concerns: how to ensure outdated versions are properly deprecated to prevent data inconsistency? *Corresponding author: Chunfu Jia (E-mail: cfjia@nankai.edu.cn).

50

The version control of blocks in blockchains is analogous to that of streaming data. Verifiable Data Streaming (VDS) protocols are designed to ensure the integrity of outsourced streaming data [7], [8]. Most existing VDS schemes rely on the Chameleon authentication tree (CAT), incurring logarithmic computation and communication overhead (i.e., log(n), where n is the number of data items) and supporting only limited item verification [7]. To address these limitations, Schröder et al. [9] proposed a more efficient, unbounded VDS protocol by treating CAT as a black box, achieving overhead logarithmic in the number of verified items. However, these VDS schemes primarily target single-item queries. Under concurrent queries, their cost grows linearly with query size. Moreover, update operations remain costly, making them unsuitable for dynamic editing. Beyond block redaction, node heterogeneity in blockchain networks further complicates the problem. Full nodes (FNs) store complete blockchain data and independently validate updates, whereas light nodes (LNs) only retain block headers and rely on FNs for verification [10]–[12]. This dependency makes LNs vulnerable to deception by malicious FNs, especially after block redactions. Malicious FNs can selectively provide old version blocks, while LNs lack effective verification methods. Therefore, ensuring efficient and reliable validation of modified blocks by LNs is thus crucial for maintaining ledger integrity [13]. Li et al. [13] proposed a blockchain-based BLIND auditing system that leverages cryptographic accumulator technology for transparent data integrity verification without a thirdparty auditor. Tian et al. [14] introduced a bi-directional shared auditing mechanism under a blockchain-based dualserver storage architecture, integrating data deduplication and auditing functions. Zhang et al. [15] designed a public auditing scheme supporting blockchain dual-replica storage, employing the HCE2 algorithm and an improved authenticator generation algorithm to achieve both auditing and deduplication [16]. However, the above schemes generally rely on the Public Key Infrastructure (PKI) certificate system, which is primarily suited for verifying the data integrity of a single user and is dif-

04

September 27,2026 at 14:28:57 UTC from IEEE Xplore. Restrictions apply.

Fig. 1. Redactable Blockchain Structure.

ficult to scale for multi-user data auditing scenarios [17]–[19]. In the VRBC (Verifiable Redactable Blockchain) application, multiple miners typically maintain the blockchain ledger [20], making the PKI-based auditing schemes unsuitable. To address the both challenges of block integrity and version control in redactable blockchains such as VRBC, VRBCIA [21] introduces a VDS protocol based on the Blockchain authentication tree (BAT), enabling integrity and consistency verification of modified blocks. Yet, it still requires commitment aggregation along block paths and retains a log(n) verify cost, which limits efficiency under high-frequency updates. To address old data deception and integrity issues in RBC scenarios, we propose EAQ-VRBC (Identity-based VDS and Auditing for Editable and Verifiable Redactable Blockchain), an efficient VRBC mechanism that integrates lightweight VDS with identity-based integrity auditing.

### A. Contributions

We propose a dynamic RSA accumulator-based revocation mechanism for RBC, where a trusted node maintains a revocation list of old block versions. Before each redactions, old versions are added to the accumulator. During queries, Auditees must provide non-membership proofs to show that the current version is not revoked, thereby ensuring data freshness and preventing old-version deceptions in VRBC. Compared to existing authentication tree-based VDS schemes, EAQ-VRBC leverages an efficient non-membership proof technique without hash-to-prime, enabling batch verification. Its generation and verification process has an operational complexity of only O(1) with lower computational cost. To address the issue of auditing in VRBC that is incompatible with PKI-based auditing, EAQ-VRBC adopts identitybased RSA signature auditing, with verification costs during the query and audit phases being relatively low.

## II. Preliminary

Redactable Blockchain: The VRBC blockchain, as shown in Fig. 1., consists of a sequence of redactable blocks Bi = (hi−1 , chi , mi , Yi , ri , ctri ), in which hi−1 , ri ∈ Z∗N ; chi , Yi ∈ QRN ; mi ∈ {0, 1}, and ctri ∈ N. Take appending block Bi as an example, Miner uses the root value mi of the Merkle hash tree (MHT) built upon transactions {T x1 , . . . , T x8 } to generate the chameleon hash value chi for the new block Bi : chi = CH(hi−1 , mi , Yi , ri ), where hi−1 is the hash value of

50

Fig. 2. System Model

the previous block, and (Yi , ri ) is the verification string of (mi , chi ) in the CH function [6]. Then, the block hash hi is generated through a standard hash function H(chi , ctri ), where ctri is the Nonce value of the block Bi . Strong RSA assumption [22]: For all λ ∈ N and probabilistic polynomial-time (ppt) adversary A, given n = pq, where p and q are poly(λ)-bit safe primes, and u ∈ Z∗n , we have:   (v, e) ← A(1λ , u, n) Pr ≤ negl(λ) v e ≡ u mod n ∧ e > 1 Shamir’s Trick [23]: For all n, x, y ∈ N, v, u ∈ Z∗N such that v x ≡ uy mod n and gcd(x, y) = 1, there exists w ∈ Z∗N such that wx ≡ u mod n.

## III. System Model

As shown in Fig. 2., EAQ-VRBC involves four entities, each with distinct responsibilities: System Manager (SM): A fully trusted authority (e.g., committee) responsible for generating system public parameters and block tags, as well as editing on-chain data upon legal or user requests. Miner: Maintains the blockchain ledger, updates versionbased revocation lists, uploads and updates blocks, and initiates audit requests. Third-Party Auditor (TPA): A light node responsible for verifying data and returning audit results during query and audit processes. Auditee (FN): A full node holding the complete ledger, responsible for verifying new blocks during redaction and generating proofs in response to TPA challenges during query and audit phases.

### A. Security model

Soundness: We define the EAQ-VRBC system security model, where the adversary A represents the SM, and the challenger C represents the Miner. The adversary A must possess all data blocks in the file or be able to guess all missing blocks; otherwise, it cannot respond to the challenge from the TPA and generate a valid proof. An adversary that does not store the data file cannot provide a storage proof

05

September 27,2026 at 14:28:57 UTC from IEEE Xplore. Restrictions apply.

for the challenged data blocks. The soundness game of EAQVRBC consists of the following phases: Setup: The challenger C initializes the parameters and  executes the algorithm Setup (1λ ) → P S, T K, pk, sk to generate the public system parameters P and key pair (pk, sk). The public system parameters P S and public key pk are sent to the adversary A. Query : The adversary A can adaptively query any verifiable tag ti for a given block Bi based on pk. The challenger C executes the algorithm Setup (1λ ) → P S, T K, pk, sk to obtain pk, executes the algorithm U pload to generate tag ti for block Bi , and returns the set of tags {ti }i∈[1,n] to the adversary A. Challenge: The challenger C generates the challenge Chal. P roof Gen: For the Chal, the adversary A runs P roof Gen (Chal) → P to generate the storage proof. Finally, the adversary A can obtain the P = {AGGE, µ}. V erif y: If the output result of the algorithm V erif y (P, Chal) → T /F is T, adversary A outputs the proof and wins the game. Controlled Redaction: Given a collision (m′s , Ys′ , rs′ ) for (ms , Ys , rs ), no adversary can extract the trapdoor key. Only redactors holding the trapdoor can forge valid collisions. Forward Dynamic Accumulator Security: Strong RSA assumption prevents FNs from misleading LNs with outdated blocks.

### B. Our Scheme

 Setup (1λ ) → P S, T K, pk, sk : The SM inputs the security parameter 1λ . The SM computes the RSA modulus ′ ′ N = pq, where p = 2p + 1 and q = 2q + 1 (both are large primes), where 2λ < φ (N ) < 2λ+1 . Define a multiplicative cyclic group QRN of quadratic residues modulo N with generator g. Define collision-resistant hash algorithms, where ∗ λ H0 , H1 , H2 , and H3 are defined as: {0, 1} ,  H0 : {0,∗ 1} → ∗ l−1 l ∗ ∗ H1 : {0, 1} → Odds 2 , 2 − 1 , H2 : ZN × ZN → ZN , ∗ ∗ H3 : {0, 1} → ZN , Υ1 : {1, 2, . . . , n}×Z∗N → {1, 2, . . . , n}, Υ n} × Z∗N → Z∗N , where l = poly(λ) satisfies √2 : {1, 2, . . . ,3/4 l ≤ τ ≤ l for any x ∈ {0, 1}∗ , P + (H1 (x)) > 2τ with overwhelming probability. τ is a tuning parameter. Set that each miner in the system has an identity identifier IDi , ∗ where IDi ∈ {0, 1} . The SM generates master public key pk = (e, N ) and master private key sk = d, such that ed ≡ 1 d (mod 4p′ q ′ ). The SM generates private key ski = H3 (IDi ) (mod N ) and public key pki = H3 (IDi ) (mod N ). We define u = QRN \ {1}. Let P P = N , and the initial value of the accumulator is set as acc (⊘) = u. Define a counter Cnt, where i = Cnt. The system maintains a revocation list of old labels R. At the same time, define upmsgi as the record of each addition operation,   for example, Each tag ′ upmsgi is a 3-tuple v, acc, acc , where: v ∈ Z∗n denotes ′

the element being added or deleted, acc, acc denote the accumulator value before and after the operation. Let file M = m1 || m2 || . . . || mn . The KGC generates trapdoor keys T K = (x, y) ∈ Z∗N , hash key HK = (X, Y ) = (g x , g y ).

50

Therefore, the public system parameters can be obtained as P S = {g, N, e, H0 , H1 , H2 , H3 , u, upmsgi , IDSM , HK}. Upload{(mi , HK, T K, P S) → Bi , ti }: Miner first investigates the hash-binding process. Miner picks at random an element ri ∈ ZN and computes the chameleon hash value of Bi : H (h ∥m ,Y )(x+y)+ri chi = (X · Y )H2 (hi−1 ∥mi ,Y ) · g1ri = g1 2 i−1 i , where hi−1 = H3 (chi−1 , ctri−1 ). Miner appends block Bi = (hi−1 , chi , mi , Y, ri ) to the blockchain when he wins the current consensus process. The SM extracts the data block hash value hs′ from the block Bs′ and generates a unique identifier in the tag as follows: hhs′ = H3 (s′ ∥hs′ ∥v), where v ∈ ZN . Q The SM then generates a tag for the block as: c n Ss′ = v d · i=1 ski s′ (mod N ), where cs′ = H0 (s′ ∥hs′ ∥v) (mod N ) and Ss′ = v d . Block tag ts′ = (Ss′ , v)Qis uploaded ′ −c n to Auditee. The TPA first computes v = Sse · i=1 pki s′ ′ (mod N ), Then it verifies the validity of the (v, Ss ) through ? H0 (s′ ∥hs′ ∥v) (mod N ) = cs′ (mod N ). Then the TPA ? verifies whether the following equation holds chi = (X · H2 (hi−1 ∥ mi ,Y ) ri Y) · g . If the verification passes, the Auditee stores the tag ts′ for the block; otherwise, the request is rejected. Redaction {(Bs , T K, HK, P S) → Bs′ }: The Miner initiates a redact request. The SM obtains the block Bs = (hs−1 , chs , ms , Ys , rs , ctrs ), where the chameleon hash value is chs , hs−1 is the hash value of the previous block, and ctrs is its Nonce value. When the message ms in the sth block needs to be updated to ms′ , the SM executes the following steps: Compute the long-term trapdoor key ks = H2 (hs−1 ∥ ms , Ys ) · (x + y) + rs mod N . Next, generate the temporary trapdoor′ ys′ for the new message ms′ : ys′ = y H3 (x, ms′ ), Ys′ = g1 s . Then, compute the new verification value rs′ = ks − H2 (hs−1 ∥ ms , Ys′ ) · (x + ys′ ) mod N . Finally, generate the collision block Bs′ = (chs , ms′ , Ys′ , rs′ ). The Auditee verifies whether the following equation holds ? chs = (X·Ys′ )H2 (hs−1 ∥ ms′ ,Ys′ ) ·g rs′ . If the verification passes, the data (ms , Ys , rs ) in the original block is replaced with the new data (ms′ , Ys′ , rs′ ), and the chameleon hash value chs remains unchanged. Query {(s, πq ) → T /F }: When the TPA wants to query whether the message m′s in the s-th block is stored in the FN, it sends an index s related to ms′ . The Auditee first retrieves the tuple (s, Bs′ , ts′ , hhs′ ) from the ledger. Then, the Auditee generates a non-membership proof for the new tag ts′ using the latest accumulator acc(R), to prove that the tag ts′ has not been revoked. First, the Auditee computes H1 (x)Q= H1 (s′ ∥hhs′ ), andQretrieves the accumulator value ′ θ = H1 (y)∈R H1 (y) = H1 (i∥hhi )∈R H1 (i∥hhi ). Next, generate the non-membership proof w̄x for x. As shown in Algorithm 1, for this update message upmsgs , we perform the following steps: First, parse upmsgs into (H1 (x) , u, u′ ). Then, update the set R ← R ∪ {H1 (x)}. Then, multiply the smooth factor dd = 1 with the Q elements in the accumulator ′ for aggregation to get θ ← H1 (y)∈R H1 (y) · dd. Next, set  ′  x ← H1 (x), and initialize s ← (1). When gcd θ , x ̸= 1,

06

September 27,2026 at 14:28:57 UTC from IEEE Xplore. Restrictions apply.

′

′

continue updating x ← x/ gcd(θ , x), and add gcd(θ , x) to ′ s . This process involves repeatedly extracting non-coprime ′ factors until x and θ become coprime. Compute a, b ∈ ZN , ′ such that: aθ + bx = 1. Then, compute B ← ub mod N . Finally, return the non-membership proof w̄x = (a, B, s). Finally, Auditee sends the data item ms and the proof πq = {ts′ , hhs′ , w̄x } to the TPA. Algorithm 1 NonMemWitCreate Input: P S, {upmsgs } Output: w̄x 1: Parse P S as (N, u); R ← ∅, dd ← (1) 2: Parse upmsgs as (H1 (x), u, u′ ) 3: Set R ← R ∪ {H1 (x)} Q Q ′ 4: θ ← H1 (y)∈R H1 (y) · |dd| i=1 dd[i] 5: x ← H1 (x); s ← (1) ′ 6: while gcd(θ , x) ̸= 1 do ′ 7: g ← gcd(θ , x); x ← x/g; s ← s ∥ g 8: Find a, b ∈ Z s.t. aθ′ + bx = 1 9: B ← ub mod n 10: return w̄x = (a, B, s)

TPA receives w̄x = (a, B, s), where s is a set of factors of x that are not coprime with the set R, storing the τ factors Q|s| of k such that s is less than or equal to 2 , i.e., i=1 s[i] = k. TPA recalculates H1 (x) = H1 (s∥hhs′ ), ′

H1 (x) Q|s|

?

and then checks whether the equalities ua·θ B i=1 s[i] = u hold to determine if x is a non-member. TPA verifies the completeness of the block Qn and −cits appended label ti by ′ calculating v = Sse · i=1 pki s′ , and then checks the ? following equality: H0 (s′ ∥hs′ ∥v) (mod N ) = cs′ (mod N ). If the above validations pass, further, the TPA checks the correctness of the chameleon hash value chs to verify the legitimacy of the data block modification using the following ? equation: chs = (X · Ys )H2 (hs−1 ∥ ms ,Ys ) · g1rs . If the equation is validated successfully, TPA will keep Bs locally; otherwise, Bs will be discarded. Audit {(Chal, P ) → T /F }: The auditing process consists of three sub-processes: Challenge, ProofGen, and Verify. TPA generates the challenge Chal = n Challenge: o ′ ′ ∗ i , r1 , r2 , where r1 , r2 ∈ ZN and i ∈ [n]. TPA sends the challenge Chal to FN. TPA generates index h α′ ii = Υ1 (i, r1 ) and coefficient βi = Υ2 (i, r2 ), where i ∈ 1, i . ProofGen:Then, the Auditee  calculates the aggregated tags Qi′ Qi′ βi AGGE = according to αi and βi . i=1 vi , i=1 Si Additionally, FN needs to aggregate the challenged block µ = Pi′ β c . In addition, we also generate an aggregated noni α i i=1 membership proof w̄x1 ,x2 ,...,xi′ as shown in Algorithm 1. The process of aggregating non-membership proofs is implemented recursively, as shown in the figure (the aggregation process of three non-membership proofs). When isDone = 0, it indicates that the aggregation is complete. The final aggregated non-membership proof result is obtained by recursively applying the algorithm to aggregate two non-membership proofs. As shown in Algorithm 2, the first step is to aggregate nonmembership proofs w̄x1 and w̄x2 . First, normalize x1 and

50

1) x2 , where x1 = QH|s11(x , | i=1 s1 [i]

2) x2 = QH|s12(x . Let a, b ∈ Z | i=1 s2 [i]

such that:ax1 + bx2 = gcd(x1 , x2 ) = dd. Next, we further simplify to obtain x1 ′ = xdd1 , x2 ′ = xdd2 . Thus, we can obtain:u = ua1 B1x1 = ua2 B2x2 . Let γ = a1 bx2 ′ + a2 ax1 ′ . ′ Thus, the above equation′ expands further to uγ mod x1 x2 ·  x 1 x 2 ′ u⌊γ/(x1 x2 )⌋ B b B a . Let a′ = γ mod x x ′ , B ′ = 1

j

γ x1 x2 ′

1 2

2

k

u · B1b B2a and s′2 = s2 ∥ (dd). Clearly, the aggregated non-membership witness is:w̄x1 ,x2 = (a′ , B ′ , s1 , s′2 ). However, verifying w̄x1 ,x2 requires roughly the same number of group operations as verifying the non-membership of x1 and x2 separately. Algorithm 2 Non-membership Witnesses Aggregation ′

Input: P S, (xj , w̄xj )i , isDone j=1 Output: w̄x1 ,x2 ,...,x ′ i ′ 1: if i = 2 then 2: Parse P S ← (N,Q u); w̄x1 ← (a1 , B1 , s1 );Q w̄x2 ← (a2 , B2 , s2 ) 3: x1 ← H1 (x1 )/ i s1 [i]; x2 ← H1 (x2 )/ i s2 [i] 4: Find a, b ∈ Z such that ax1 + bx2 = gcd(x1 , x2 ) 5: x′1 ← x1 / gcd(x1 , x2 ); x′2 ← x2 / gcd(x1 , x2 ) 6: s′2 ← s2 ∥ gcd(x1 , x2 ) 7: γ ← a1 bx′2 + a2 ax′1 ; a′ ← γ mod (x1 x′2 ) ′ 8: B ′ ← u⌊γ/(x1 x2 )⌋ B1b B2a mod N 9: if isDone = 0 then 10: return w̄x1 ,x2 = (a′ , B ′ , s1 , s′2 ) 11: else ′ ′ 12: C ← ua mod N ; D ← B ′x1 x2 mod N 13: πC ← NI-SimPoE.Prove(u, C, a′ ) 14: πD ← NI-SimPoE.Prove(x1 x′2 , D, B ′ ) 15: return [C, a′ , s1 , s′2 , D, B ′ , πC , πD ] 16: else if i′ > 2 then 17: w̄x1 ,x2 ← NonMemAgg(P S, u, (x1 , w̄x1 ), (x2 , w̄x2 ), 0) 18: for j = 3 to i′ − 1 do 19: M ← NonMemAgg(P S, u, {(xk )j−1 k=1 , w̄x1 ,...,xj−1 , xj , w̄xj }, 0) 20: w̄x1 ,...,xj ← M

21:

′

−1 return NonMemAgg(P S, u, {(xj )ij=1 , w̄x1 ,...,x ′

i −1

, xi′ , w̄x ′ }, 1) i

Algorithm 3 Verify Non-membership Witnesses Aggregation ′

Input: P S, {(xj , w̄xj )}ij=1 Output: valid/invalid 1: Parse P S ← (N, u) 2: Parse w̄x1 ,...,xi′ ← (a′ , B ′ , s1 , . . . , si′ , πC , πD , C, D) 3: for i = 1 to i′ do 4: for j = 1 to |sxi | do 5: if sxi [j] > 2τ then 6: return invalid Q|sx | 7: xi ← H(xi )/ k=1i sxi [k]

8: if NI-SimPoE.Verify(u, C, a′ , πC ) = 0 then Q′ 9: if NI-SimPoE.Verify(B ′ , D, ii=1 xi , πD ) = 0 then 10: if CD ≡ u (mod N ) then 11: return valid 12: return invalid

To address this issue, we use NI-SimPoE (The detailed process of generating the proof can be found in reference [24]) to compute the proofs πC,(x1 ,x2 ) and πD,(x1 ,x2 ) for the statements (A, C, γ) and (B ′ , D, x1 x2 ′ ) respectively, where: ′ C = uγ , D = B ′x1 x2 . Finally, we define the full witness as: ′ ′ w̄x1 ,x2 = (a , B , sx1 , s′x2 , πC,(x1 ,x2 ) , πD,(x1 ,x2 ) , C, D). Next, the aggregated non-membership proof w̄x1 ,...,xi′ is recursively computed using the method  shown in the figure. Auditee sends the integrity proof P = AGGE, µ, w̄x1 ,...,xi′ to TPA.

07

September 27,2026 at 14:28:57 UTC from IEEE Xplore. Restrictions apply.

Verify: After receiving P , TPA determines whether the data blocks and their tags are complete by verifying the following equation: ′ i Y

Sαeβi i

 ′  i n Y β Y µ (mod N ) =  vi i · H3 (IDi ) 

i=1

i=1

(mod N )

i=1

(1)

Next, TPA verifies w̄x,y according to Algorithm 3. First, it checks whether there are any non-prime factors in the set s; if any are found, it directly returns ”invalid.” Then, each xi is normalized. Following that, TPA checks the correctness of the knowledge about C and D by verifying the PoE equation. If both are correct, it checks whether the non-membership proof equation: CD ≡ u (mod N ) holds. If it holds, TPA returns ”valid,” indicating the verification is successful. Update{(P S, mss′ , R) → R′ , Bss′ }: To replace a previously outsourced data item m′s with a new one m′ss , the Miner first retrieves the current tuple (s′ , Bs′ , t′s ) from the Auditee, ? and then checks its validity through H0 (s′ ∥hs′ ∥v) mod N = cs′ mod N . If it passes the verification, Miner creates tss′ = (Sss′ , v), and updates the current accumulator acc(R) ← H s′ ∥hh′s ) (acc(R)) ( . Furthermore, Miner sends (ss′ , mss′ , tss′ ) and acc(R) to Auditee. After that, Auditee checks the validity of tss′ again and excutes the redaction algorithm to replace (s′ , ms′ , ts′ , hhs′ ) with (ss′ , mss′ , tss′ , hhss′ ). If it passes the verification. Finally, Miner updates R ← R ∪ {hhs′ = H3 (s′ ∥hs′ ∥ms′ )} . In addition, SM uses the updated accumulator acc(R) to update the public parameter P S.

## IV. Security Analysis

Theorem 1.(Correctness): EAQ-VRBC ensures correct verification during the block query and audit stages. Proof: Based on similar concepts, the correctness of blockchain auditing can be inferred from the block query phase. Therefore, we will prove this by following two steps. Step 1: We will prove the correctness of the block query in equation 2, including the non-membership proof and integrity tag verification. H(x) Q|s| s[i] i=1

′

ua·θ · B

H(x)

= ua·

y∈R H1 (y)

b Q|s|

·u

i=1

s[i]

′

(2)

= ua·θ +bx = u t′s ·

n Y

−cs′

H (IDi )

=v·

i=1

=v ′ ′ H0 (s ∥hs ∥v)mod = cs′

n Y

c

H (IDi ) s′ ·

i=1

n Y

H (IDi )

−cs′

i=1

(mod N ) (3)

The correctness of the integrity tag equation is shown in equation 3. Step 2: We will prove the correctness of the block audit, including the non-membership proof and integrity tag verification equations 4 and 5.

50

Theorem 2.(Soundness): The security of the auditing process relies on the RSA assumption, especially for large public exponents. If the RSA assumption holds, no PPT adversary A can break the protocol with non-negligible probability. u = uax1 +bx2

′

bx2 ′

ax ′

= (ua1 B1x1 )

· (ua2 B2x2 ) 1  x1 x2 ′ ′ ′ = ua1 bx2 +a2 ax1 · B1b B2a  x1 x2 ′ ′ ′ = uγ mod x1 x2 · u⌊γ/(x1 x2 )⌋ B1b B2a = CD

(4)

Proof: The above theorem is proven through the interaction between the adversary A and the simulator algorithm B. Setup: B initializes system parameters to generate public system parameters PS = {g, N, e, H0 , H1 , H2 , H3 , u, upmsgi , IDSM , HK} and public key pk. Then, B generates hash values hhs′ = H3 (s′ ∥hs′ ∥v) based on the block hash value hs′ and forges tags ti . B sends the tuples W = {ti }i∈[1,n] to the adversary A. B and A perform the challenge-proof steps in the auditing process, where B acts as TPA and A acts as Auditee. A can obtain the auditing results after verification. Finally, A outputs the forged tags. ′ ′ !βi i i n Y Y Y cαi e·βi Sαi (mod N ) = vi · H3 (IDi ) i=1

i=1

i=1

′

=

i Y

′

vi

βi

·

i=1

=

vi βi ·

i=1

=

·βi

n Y

H3 (IDi )

Pi′

i=1 cαi ·βi

i=1

′

i Y

c

H3 (IDi ) αi

i=1 i=1

′

i Y

i Y n Y

vi βi ·

i=1

n Y

H3 (IDi )

µ

(mod N )

i=1

(5) ′ i Y

Sαeβi i =

i=1 ′

i Y i=1

′ i Y

i=1 ′

′

eβ S ′ αi i =

viβi ·

i Y i=1

′

β v′ i i ·

n Y

n Y

pkiµ

(mod N ),

i=1

(6) µ′

H(IDi )

(mod N )

i=1

Next, we provide a proof of the correctness of the auditing scheme. Assuming that the adversary A outputs a response P ′ = {AGGE ′ , µ′ }. The record of Auditee’s correct response is P =  {AGGE, µ}. The correct  proof is ′composed of Qi′ Qi′ Pi βi AGGE = and µ = i=1 βi cαi . The i=1 vi , i=1 Si adversary A outputs P ′ ̸= P . Based on the correctness of Theorem 1, the two equations in equation 6 will all pass verification. Since µ′ ̸= µ, let’s define ∆µ = µ − µ′ . Next, divide the above two verification equations to obtain:

08

September 27,2026 at 14:28:57 UTC from IEEE Xplore. Restrictions apply.

 ′ e  ′ e i i Y Y ′ ′ i  Sαe·βi (modN ) /  Sαe·β (modN ) (modN ) i i

i=1

i=1

Qi′

= Qi=1 ′ 

Qi′

n

vi βi Y

′ i ′ βi i=1 i=1 vi

e

pki∆µ (modN )

Qi′ n vi βi Y ∆µ  (modN ) = Qi=1 pki ′ ′ β′ ′ i i i ′ βi i=1 i=1 Sαi i=1 vi βi i=1 Sαi

Q ′

(mod N ) (7)

Qn

i=1 pki = k ∗ ZN , then we have:

Let

e

· y d and be =

Qi′

e

Q ′





βi i=1 Sαi

′ β′ i i i=1 Sαi

e βi S i=1 αi   ′ β′ Qi′ k ∆µ · b · i=1 Sαii 

Qi′

Qi′ βi i=1 vi Qi′ β′ ′ i i=1 vi

, where k, b ∈

(mod N ) = be · k e∆µ · y d∆µ

(mod N ) = y d∆µ (8) e

If gcd (e, d∆µ) = 1, then we can find x∗ such that (x∗ ) = y. This means we can break the RSA hard problem. However, since e is a large public prime number and ∆µ = µ′ − µ < e, we can deduce that gcd (e, ∆µ) = 1. Therefore, we can get d · e · ∆µ ≡ ∆µ (mod e) and gcd (e, d∆µ) ̸= 1, which implies d∆µ  λ≡  0 mod e. As the value of d is chosen from the range 1, 2 , the advantage of breaking the RSA hard problem is at most 2−λ , which is negligible. Therefore, the adversary A cannot forge a response P ′ = {AGGE ′ , µ′ } that passes the TPA verification to solve the RSA hard problem. In other words, they cannot forge a valid e aggregated signature AGGE ′ that makes (x∗ ) = y. (Controlled redaction):The scheme enables controlled redaction via double-trapdoor chameleon hashing, ensuring collision resistance and key security—adversaries cannot forge or steal keys. (Forward Dynamic Accumulator Security): Under the random oracle model, the security of the RSA accumulator is guaranteed if the following conditions are satisfied: (1) the hash function H1 is collision-resistant, and (2) the adaptive root assumption holds in the RSA group. The basic security of the RSA accumulator is further ensured by Shamir’s Trick (via efficient computation of RSA inversion) and ultimately relies on the strong RSA assumption. Proof details are omitted due to space constraints.

## V. Performance Evaluation

### A. Experimental parameter configuration

We implement AMVA17 [6] and VRBCIA [21] in Python using Petlib and py_ecc. On-chain gas costs are measured on Ethereum’s Ropsten testnet, and off-chain computations

50

are run on a machine with a 12th Gen Intel Core i9-12900H (2.50 GHz), 16GB RAM, under Ubuntu 22.04.5 LTS. EAQVRBC uses a 2048-bit RSA modulus N , providing 112-bit security. Each block contains 16 bytes of data. Experiments are averaged over 30 runs. Parameters are listed in Table I.

### B. Theoretical Analysis

As shown in Tables II and III, during the setup phase, AMVA17 [6], VRBCIA [21], and EAQ-VRBC all publish system public parameters and incur a cost of 1M to generate the genesis block. The basic communication overhead for packaging and transmitting transactions is 1|BH| + m|Tx |. In the upload phase, AMVA17 uploads only the block’s basic information (e.g., hash index, MHT hash value), while VRBCIA additionally uploads the block’s commitment values and incurs an overhead of q|G| to pre-generate commitment values for child nodes. EAQ-VRBC, besides uploading basic information, requires an extra 2(ni + 1)Exp + 2(ni − 1)Mul for calculating and verifying the label based on the block’s chameleon hash value. In the redact phase, AMVA17 performs chameleon hash verification, while VRBCIA incurs an additional cost of L(h+Exp) to update commitments on the node’s path, where L is the height of the redacted node in BAT. Since EAQ-VRBC generates block labels from the chameleon hash value, no update is needed. In the Query phase, as AMVA17 lacks a challenge-proof phase, we compare VRBCIA and EAQ-VRBC. VRBCIA costs qLH + (2N -1)Exp + 2(c − 1)Mul to return commitment proofs for all parent and child nodes on the queried block’s path, where N is the family vector’s dimension. EAQ-VRBC requires (l+1)H + Inv + Mul + Exp to generate the nonmembership proof. In the Audit phase, VRBCIA incurs costs for returning commitment proofs of all parent and child nodes along the challenged block paths, covering cρ nodes, where ρ is the number of summary nodes on the path of the challenged node. EAQ-VRBC requires (6c - 6)Exp + 2(c-1)Inv + 3(c1)Mul + c · 2l+1 H to generate the aggregated proof. The communication cost in the verify phase is |ZN | + |QRN |.

### C. On-Chain Cost

As shown in Figure. 3., we evaluated the on-chain (gas) costs across the Upload, Redact, Query, and Audit phases. In the Setup phase, gas consumption remained stable: AMVA17 required 0.53768 × 105 Gwei, VRBCIA 0.81311 × 105 Gwei (with BAT parameters: q = 2, level= 4, total nodes= 15), and EAQ-VRBC 0.71768 × 105 Gwei. In the Upload phase, uploading each block cost 0.71769 × 105 Gwei for AMVA17, 0.81025 × 105 Gwei for VRBCIA (including child node commitments), and 0.254526 × 106 Gwei for EAQ-VRBC, with 90.3% attributed to tag storage and verification. In the Redact phase, costs were as follows: VRBCIA: 0.81037 × 105 Gwei, AMVA17: 0.53768 × 105 Gwei, EAQVRBC: 0.104788 × 106 Gwei, with costs for both adding and modifying blocks. In the Query phase, VRBCIA incurred 0.145671 × 106 Gwei due to the aggregation of commitments and labels, while EAQ-VRBC reduced the cost to 0.132913 ×

09

September 27,2026 at 14:28:57 UTC from IEEE Xplore. Restrictions apply.

Qtable I NOTATIONS Notation

Description

n ni m q r l c H M Inv Exp Pair |QRN |/|G| |Zp |/ |ZN | |T x|; |BH| |index|

Number of blocks in the blockchain Number of miners Number of transactions in a standard block Number of forks in the q-ary BAT Number of nodes in the path union Height of the MHT in the block Number of challenged blocks Cost of running a hash function Cost of mining a standard block The modular inverse operation Cost of exponentiation operation Cost of bilinear pairing operation Size of elements in QRN / G Size of elements in Zp / ZN Size of a transaction;Size of the block header Index size of the challenged data block.

Fig. 3. On-chain cost of steps: (a) Setup; (b) Upload; (c) Redact; (d) Query; (e) Audit.

106 Gwei by using non-membership proof and label values. In the Audit phase, VRBCIA’s cost was 0.157225 × 106 Gwei for aggregation of node commitments, while EAQVRBC maintained a constant cost of 0.158336 × 106 Gwei by aggregating non-membership proof and integrity tags.

### D. Off-chain cost

Since AMVA17 does not include the Query and Audit steps, we compared the off-chain computation costs of our scheme with VRBCIA during these phases. The experimental results are shown in Figures 4, 5, 6, 7, 8, and 9. a) Query phase: In the Proof generation sub-stage, EAQ-VRBC leverages modular exponentiation and hashing to generate block tags and non-membership proofs, reducing computation by 99% compared to VRBCIA’s aggregation of commitments and hashes along query paths. In the Proof verification sub-stage, EAQ-VRBC verifies block tags and nonmembership proofs, achieving 99.7% higher efficiency than VRBCIA, which requires costly exponentiation and pairing operations. b) Audit phase: In the Proof generation sub-phase, EAQVRBC primarily incurs a cost of generating aggregated nonmembership proofs, with the former accounting for 93.75% of the total. VRBCIA’s cost mainly stems from aggregating commitments and hashes along all challenge paths. EAQ-VRBC achieves a 94.3% efficiency improvement over VRBCIA. In

51

the Proof verification sub-phase, EAQ-VRBC verifies only one aggregated proof and partially delegates verification on-chain, while VRBCIA still performs complex pairing checks. EAQVRBC’s verification cost is about 98.6% lower than VRBCIA.

### E. Conclusion

In conclusion, EAQ-VRBC resists old data deception in RBC by introducing a revocation mechanism based on dynamic RSA accumulators, ensuring only the latest data versions remain valid. It achieves a verification cost in querying and auditing (including non-membership proofs and identitybased RSA tags) that is approximately one order of magnitude lower than existing solutions. Experimental results show that EAQ-VRBC significantly lowers off-chain costs, offering a scalable and efficient solution for large-scale blockchain systems. ACKNOWLEDGMENT This work was supported in part by the National Natural Science Foundation of China under Grants 62172238, and in part by the National Key R&D Program of China under Grant 2018YFA0704703.

## References

[1] G. Wood et al., “Ethereum: A secure decentralised generalised transaction ledger,” Ethereum project yellow paper, vol. 151, no. 2014, pp. 1–32, 2014.

[2] M. Andrychowicz, S. Dziembowski, D. Malinowski, and Ł. Mazurek, “Secure multiparty computations on bitcoin,” Communications of the ACM, vol. 59, no. 4, pp. 76–84, 2016.

[3] V. P. Ranganthan, R. Dantu, A. Paul, P. Mears, and K. Morozov, “A decentralized marketplace application on the ethereum blockchain,” in 2018 IEEE 4th International Conference on Collaboration and Internet Computing (CIC). IEEE, 2018, pp. 90–97.

[4] M. Li, J. Weng, A. Yang, W. Lu, Y. Zhang, L. Hou, J.-N. Liu, Y. Xiang, and R. H. Deng, “Crowdbc: A blockchain-based decentralized framework for crowdsourcing,” IEEE transactions on parallel and distributed systems, vol. 30, no. 6, pp. 1251–1266, 2018.

[5] J. M. L. Alfonsı́n, “Argentina: The right to be forgotten,” in The Right to Be Forgotten: A Comparative Study of the Emergent Right’s Evolution and Application in Europe, the Americas, and Asia. Springer, 2020, pp. 239–248.

[6] G. Ateniese, B. Magri, D. Venturi, and E. Andrade, “Redactable blockchain–or–rewriting history in bitcoin and friends,” in 2017 IEEE European symposium on security and privacy (EuroS&P). IEEE, 2017, pp. 111–126.

[7] D. Schröder and H. Schröder, “Verifiable data streaming,” in Proceedings of the 2012 ACM conference on Computer and communications security, 2012, pp. 953–964.

[8] J. Krupp, D. Schröder, M. Simkin, D. Fiore, G. Ateniese, and S. Nürnberger, “Nearly optimal verifiable data streaming,” in PublicKey Cryptography–PKC 2016: 19th IACR International Conference on Practice and Theory in Public-Key Cryptography, Taipei, Taiwan, March 6-9, 2016, Proceedings, Part I. Springer, 2016, pp. 417–445.

[9] D. Schöder and M. Simkin, “Veristream–a framework for verifiable data streaming,” in International conference on financial cryptography and data security. Springer, 2015, pp. 548–566.

[10] A. Palai, M. Vora, and A. Shah, “Empowering light nodes in blockchains with block summarization,” in 2018 9th IFIP international conference on new technologies, mobility and security (NTMS). IEEE, 2018, pp. 1–5.

[11] S. Cao, S. Kadhe, and K. Ramchandran, “Cover: Collaborative lightnode-only verification and data availability for blockchains,” in 2020 IEEE International Conference on Blockchain (Blockchain). IEEE, 2020, pp. 45–52.

10

September 27,2026 at 14:28:57 UTC from IEEE Xplore. Restrictions apply.

TABLE COMPARISONS OF COMMUNICA System AMVA17 [6] VRBCIA [21] EAQ-VRBC

Setup 1|BH| + m |Tx | + 2 (|Zp | + |G|) 1 |BH| + m |Tx | + 4 (N + 1) |G| 1 |BH| + m |Tx | + n |ZN | + 2 |QRN |

Upload 1 |BH|+m |Tx |+|G|+2 |Zp |

Redaction 1 |BH| + m

1 |BH| + m |Tx | + (q + 1) |G| + 2 |Zp | 1 |BH| + m |Tx | + 2 |ZN | + 2 |QRN |

1 |BH| + m 2 |Zp | 1 |BH| + m

TABLE COMPARISONS OF COM System AMVA17 [6] VRBCIA [21]

Setup 1M + 1H + 3Exp 1M + 2qH + 3N Exp

Upload 1M + (2l+1 + 2)H + 4Exp 1M+(2l+1 +3q+2)H+(N + q + 1)Exp + 2Mul

Redaction (2l+1 + 2)H (2l+1 + 2L 1)Exp + 3M

EAQ-VRBC

1M + (n + 2)Exp + (6 + ni)H

1M + (2l+1 + 4)H + 2(ni + 3)Exp + 2(ni − 1)Mul

(2l+1 + 5)H

Fig. 4. Computation of proof generation in Audit

Fig. 5. Computation of Audit

Fig. 7. Computation of proof verification in Query

Fig. 8. Computa

[12] D. Derler, K. Samelin, D. Slamanig, and C. Striecks, “Fine-grained and controlled rewriting in blockchains: Chameleon-hashing gone attributebased,” Cryptology ePrint Archive, 2019.

[13] S. Li, C. Xu, Y. Zhang, Y. Du, and K. Chen, “Blockchain-based transparent integrity auditing and encrypted deduplication for cloud storage,” IEEE Transactions on Services Computing, vol. 16, no. 1, pp. 134–146, 2022.

[14] G. Tian, Y. Hu, J. Wei, Z. Liu, X. Huang, X. Chen, and W. Susilo, “Blockchain-based secure deduplication and shared auditing in decentralized storage,” IEEE Transactions on Dependable and Secure Computing, vol. 19, no. 6, pp. 3941–3954, 2021.

[15] Q. Zhang, D. Sui, J. Cui, C. Gu, and H. Zhong, “Efficient integrity auditing mechanism with secure deduplication for blockchain storage,” IEEE Transactions on Computers, vol. 72, no. 8, pp. 2365–2376, 2023.

[16] G. Ha, X. Ge, C. Jia, Y. Chen, and Z. Su, “Revisiting sgx-based encrypted deduplication via pow-before-encryption and eliminating redundant computations,” IEEE Transactions on Dependable and Secure Computing, 2024.

[17] W. Shen, J. Yu, M. Yang, and J. Hu, “Efficient identity-based data integrity auditing with key-exposure resistance for cloud storage,” IEEE Transactions on Dependable and Secure Computing, vol. 20, no. 6, pp. 4593–4606, 2022.

[18] F. Ullah, C.-M. Pun, M. I. Mohmand, R. K. Mahendran, A. A. Khan, S. M. Alhammad, J. J. Rodrigues, and A. Farouk, “Privacy-aware secure data auditing for cloud-based intelligence of things environment,” IEEE

51

EII

ATION AND STORAGE COSTS .

m |Tx | + 3 |Zp |

m |Tx | + 2 |G| +

m |Tx | + 3 |ZN |

Block query (Prove&Verify) -

Audit (Prove&Verify) -

1 |BH| + m |Tx | + (L + 4) |G| + 4 |Zp | + |index| 1 |BH| + m |Tx | + 2 |ZN | + 2 |QRN | + |index|

ρc(1 |BH| + m |Tx |) + (3ρ + 1)(|G| + |Zp |) c(1 |BH| + m |Tx |) + (c + 4) |ZN | + 6 |QRN |

EIII

MPUTATION COSTS .

H + 3Exp + 4)H + 2(L + M ul

H + 4Mul + 2Exp

Block query (Prove&Verify) (qL+2l+1 )H+(2N +1+L)Exp+ (L + 2)Pair + 2(c − 1)Mul 7Exp + (2l+1 + 4 + rl)H + Inv + 6Mul

f proof verification in

ation of upload

Audit (Prove&Verify) cρ(q + 1 + 2l+1 )H + (2N + cρ)Exp + (cρ + 1)Pair + 2(c − 1)(ρ − 1)Mul (8c − 8)Exp + 2(c − 1)Inv + (5c − 4) · Mul + c · 2l+1 H

Fig. 6. Computation of proof generation in Query

Fig. 9. Computation of redact

Internet of Things Journal, 2025.

[19] T. Li, J. Chu, and L. Hu, “Cia: A collaborative integrity auditing scheme for cloud data with multi-replica on multi-cloud storage providers,” IEEE Transactions on Parallel and Distributed Systems, vol. 34, no. 1, pp. 154–162, 2022.

[20] J. Shen, X. Chen, Z. Liu, and W. Susilo, “Verifiable and redactable blockchains with fully editing operations,” IEEE Transactions on Information Forensics and Security, vol. 18, pp. 3787–3802, 2023.

[21] G. Tian, J. Wei, M. Kutyłowski, W. Susilo, X. Huang, and X. Chen, “Vrbc: A verifiable redactable blockchain with efficient query and integrity auditing,” IEEE Transactions on Computers, vol. 72, no. 7, pp. 1928–1942, 2022.

[22] N. Barić and B. Pfitzmann, “Collision-free accumulators and fail-stop signature schemes without trees,” in International conference on the theory and applications of cryptographic techniques. Springer, 1997, pp. 480–494.

[23] A. Shamir, “On the generation of cryptographically strong pseudorandom sequences,” ACM Transactions on Computer Systems (TOCS), vol. 1, no. 1, pp. 38–44, 1983.

[24] B. Wesolowski, “Efficient verifiable delay functions,” Journal of Cryptology, vol. 33, no. 4, pp. 2113–2147, 2020.

11

September 27,2026 at 14:28:57 UTC from IEEE Xplore. Restrictions apply.
