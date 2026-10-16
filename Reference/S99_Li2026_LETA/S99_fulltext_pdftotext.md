# LETA: A Lattice-Based Efficient and Traceable Privacy-Preserving Batch Authentication Scheme for Vehicle Platoon in VANETs

> Full text extracted from `LETA_A_Lattice-Based_Efficient_and_Traceable_Privacy-Preserving_Batch_Authentication_Scheme_for_Vehicle_Platoon_in_VANETs.pdf` with `pdftotext`. Equations, tables and figures embedded as images or complex layout may be garbled or missing; check the PDF for those.

2186

IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS, VOL. 44, 2026

LETA: A Lattice-Based Efficient and Traceable
Privacy-Preserving Batch Authentication
Scheme for Vehicle Platoon in VANETs
Qichang Li , Graduate Student Member, IEEE, Yingjie Xia , Senior Member, IEEE, Xuejiao Liu ,
Xiyuan Chen , Zhiquan Liu , Zhen Guo, Member, IEEE, Zhe Liu , Senior Member, IEEE,
and Liming Fang , Member, IEEE
Abstract—Vehicle platoon (VP), as a typical form of traffic
cooperation, can significantly enhance traffic efficiency and safety
in Vehicular Ad hoc Networks (VANETs). However, malicious
vehicles in VP poses a severe threat to the security of entire
VP, requiring to be efficiently traced by identity authentication.
In this paper, we propose a lattice-based efficient and traceable privacy-preserving batch authentication scheme for vehicle
platoon in VANETs, named LETA. First, we design a dynamic
VP identity structure VPD-Tree which is constructed based on
hash tree and pseudonyms of vehicles to preserve privacy. Then,
an aggregate signature is constructed based on VPD-tree and
modular lattice for secure and efficient batch authentication of
VP. Finally, Zero-Knowledge Proofs (ZKP) is applied on the
VPD-Tree structure to anonymously and efficiently trace the
malicious vehicles of VP. Security analysis shows that LETA
achieves stronger security guarantees, thereby offering a more
secure solution than existing approaches. Moreover, performance
evaluations show that LETA achieves lower computation and
communication overheads through the VPD-tree structure and
efficient batch authentication scheme.
Index Terms—Vehicle platoon, batch authentication, aggregation signature, privacy-preserving, efficient traceability.

W

I. I NTRODUCTION
ITH the rapid development of Vehicular Ad hoc Networks (VANETs), vehicle platoon (VP) has become

Received 12 February 2025; revised 15 August 2025; accepted 21 November 2025. Date of publication 25 November 2025; date of current version
18 February 2026. This work was supported in part by the National Natural
Science Foundation of China under Grant 62472132 and in part by the Key
Research and Development Program Project of Zhejiang Province under Grant
2024C01179. (Corresponding author: Yingjie Xia.)
Qichang Li is with the Micro-Electronics Research Institute, Hangzhou
Dianzi University, Hangzhou 310018, China.
Yingjie Xia is with the Micro-Electronics Research Institute, Hangzhou
Dianzi University, Hangzhou 310018, China, also with the College of Computer Science and Technology, Zhejiang University, Hangzhou 310012, China,
and also with Hangzhou Yuantiao Technology Company, Hangzhou 310036,
China (e-mail: xiayingjie@zju.edu.cn).
Xuejiao Liu is with the School of Information Science and Technology,
Hangzhou Normal University, Hangzhou 311121, China.
Xiyuan Chen is with the College of Computer Science, Hangzhou Dianzi
University, Hangzhou 310018, China.
Zhiquan Liu is with the College of Cyber Security, Jinan University,
Guangzhou 510632, China.
Zhen Guo is with the School of Cyberspace Security (School of Cryptography), Hainan University, Haikou 570228, China.
Zhe Liu is with Zhejiang Laboratory, Hangzhou, Zhejiang 311121, China.
Liming Fang is with the College of Computer Science and Technology,
Nanjing University of Aeronautics and Astronautics, Nanjing, Jiangsu 210016,
China.
Digital Object Identifier 10.1109/JSAC.2025.3636982

an important approach for traffic collaboration which can
significantly enhance traffic efficiency and safety in various
application scenarios. VP refers to a group of vehicles that
travel together in a coordinated manner, maintaining close
distances and synchronizing their movements through intervehicle communication. For instance, during peak hours, a
platoon of buses can effectively alleviate traffic congestion
and reduce energy consumption [1]. In freight transportation,
well-coordinated truck platoons can improve transportation
efficiency and reduce air resistance, thereby decreasing fuel
consumption [2]. In military scenarios, automated vehicle platoons can reduce unreliability of human operation [3], thereby
improving the accuracy of execution. Due to the coordination
and cooperation required among multiple vehicles in VP, the
presence of malicious vehicles could pose a serious threat to
the security of entire platoon [4]. Therefore, it is essential to
ensure that all vehicles in the VP are legitimate and trusted
participants, and the malicious vehicles can be efficiently and
accurately traced if present.
In order to effectively verify the legitimacy of all vehicle
identities in VP, the authentication scheme is required to be
designed with three aspects of characteristics. (1) For verifying
multiple vehicle identities of VP, it is crucial to design an
efficient authentication scheme that reduces computational cost
while maintaining strong security [5]. (2) During authentication for vehicles in VP, the privacy of vehicles is required to
be strictly preserved to prevent identity fraud and information
leakage. (3) If there existing malicious vehicles in VP, they are
required to be efficiently and accurately identified and traced
to maintain stability and security of the entire platoon [6].
Aiming to fulfill the characteristics above, some batch
authentication schemes are proposed for efficiently verifying
the legitimacy of vehicle identities within the platoon. These
work primarily include methods based on bilinear pairings
[7], [8] and Elliptic Curve Cryptography (ECC) [9], [10],
[11]. However, with the rise of quantum attack, the security
capability of these traditional methods becomes increasingly
vulnerable. Therefore, researchers choose some stronger cryptographic techniques to design the authentication schemes
to resist quantum attacks, such as lattice-based cryptography
[12], [13], [14]. Although these lattice-based authentication schemes offer enhanced security, they come with the
drawback of higher computation and communication costs.

1558-0008 © 2025 IEEE. All rights reserved, including rights for text and data mining, and training of artificial intelligence and
similar technologies. Personal use is permitted, but republication/redistribution requires IEEE permission.
See https://www.ieee.org/publications/rights/index.html for more information.
Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

LI et al.: LATTICE-BASED EFFICIENT AND PRIVACY-PRESERVING BATCH AUTHENTICATION SCHEME

Additionally, when batch authentication fails due to the presence of malicious vehicles, tracing those vehicles in the VP
typically requires re-authentication of all vehicle identities
[15] or verification of other auxiliary information [16]. These
VP batch authentication and malicious vehicle tracing tasks
not only incur higher computational and communication costs
but also raise potential risks of privacy leakage, particularly
in the VP with many vehicles constantly sharing sensitive
information.
To address the aforementioned issues, we propose a
lattice-based efficient and traceable privacy-preserving batch
authentication scheme for vehicle platoon in VANETs, named
LETA. Specifically, the scheme consists of three components.
First, a dynamic VP integrated identity structure VPD-Tree is
constructed based on the hash tree and pseudonyms of vehicles, embedding cryptographic randomness to protect against
privacy leakage and prevent identity linkage attack. Second, an
aggregated signature is designed through utilizing VPD-Tree
and modular lattice to enable secure and efficient batch authentication for all vehicles in VP. Third, Zero-Knowledge Proofs
(ZKP) is applied on the VPD-Tree structure to implement an
anonymous and efficient malicious vehicles tracing method,
allowing for quick identification of malicious vehicles without
compromising privacy. Therefore, the main contributions can
be summarized as follows.
1) The hash tree-based VPD-Tree structure is designed
by the nodes constructed by pseudonyms and other
information of each vehicle in VP with the partial update
mechanism, enabling dynamic VP integrated identity
construction, efficient VPD-Tree update and effective
privacy preservation.
2) The lattice-based aggregate signature is designed by
generating vehicle hash values from VPD-Tree and
reducing VP signature size through modular lattice,
thereby achieving secure and efficient batch authentication for all vehicles in VP.
3) The malicious vehicle tracing method leverages the
hierarchical structure of VPD-Tree to quickly locate suspected malicious vehicles and uses ZKP in the tree nodes
to verify vehicle identity without disclosing confidential
information, thereby enabling anonymous and efficient
trace in VP.
The structure of remaining parts of this paper is organized as
follows. Section II reviews related work. Section III provides
an overview of the LETA architecture, and Section IV details
implementation of the LETA scheme. The security analysis
and performance experiments are conducted in Section V and
Section VI respectively. Finally, Section VII concludes the
paper.
II. R ELATE W ORK
A. Authentication Schemes for Vehicle Platoons in VANETs
Authentication in VANETs, particularly for VP, is complex
due to the dynamic nature of the network, the high mobility
of vehicles, and the need for fast, efficient communication
protocols. Several methods have been proposed to authenticate
vehicles in such environments, each with its own strengths and

2187

limitations. These include traditional public key infrastructure
(PKI)-based methods, identity-based cryptography (IBC), and
certificateless cryptography (CLC).
Asghar et al. [17] proposed a similar PKI-based authentication protocol for VANETs. However, as the number of
revoked vehicles grows, the efficiency of identifying revoked
vehicles from the Certificate Revocation Lists (CRL) becomes
relatively low. In general, PKI schemes suffer from high
computational overhead, require complex certificate management, and are vulnerable to scalability issues in dynamic
environments like VANETs. Cui et al. [18] proposed a privacypreserving authentication scheme based on a cuckoo filter,
which leveraged the cuckoo filter and binary search to enhance
batch verification. Zhang et al. [19] employed bilinear pairingbased signature technology to safeguard their scheme against
collusion and replay attacks. However, IBC-based schemes
faced challenges such as increased computational complexity,
scalability issues in large-scale networks, and potential vulnerabilities to advanced attacks like adaptive collusion. To address
some of the issues with traditional PKI and IBC schemes,
the use of CLC has been proposed. Yadav and Vijayakumar
[20] proposed a signature-based authentication protocol for
VANETs that provided an authentication solution for vehicles,
Roadside Units (RSUs), and Trusted Authorities (TAs). Nath
and Choudhury [11] introduced a privacy-preserving authentication scheme for VANETs, in which authenticated vehicles
communicated using a group key. To prevent traceability
attacks, vehicles were required to request pseudonym updates
from the TA.
However, unlike traditional VANETs, VP is characterized
by a structured and tightly coordinated topology. Therefore,
existing authentication schemes lack the scalability required
to handle the high mobility and dynamic changes inherent to
VP scenarios.
B. Batch Authentication for Vehicle Platoons in VANETs
In VANETs, batch authentication improves efficiency by
simultaneously verifying multiple vehicles, thereby reducing
both computational and communication overhead. Existing
techniques include group signatures [21], ring signatures [22],
and aggregate signatures. Among them, aggregate signatures
offer significant advantages by combining multiple individual
signatures into a single compact one, making the process more
efficient than group or ring signatures. This further optimizes
the authentication workflow by enhancing speed and scalability, while also reducing communication and computational
cost.
In 2003, Boneh et al. [23] proposed the concept of aggregate
signatures, which combine n individual signatures into a
single short signature, significantly reducing message size and
authentication overhead. Zhang et al. [24] proposed an identity
authentication scheme based on aggregate signatures, bilinear pairings, and temporary pseudonyms. It ensured secure
vehicle authentication, message validation, and tracking prevention, while maintaining strong performance and resilience
to security threats. Ali et al. [25] proposed an efficient and
secure certificateless short signature-based conditional privacypreserving authentication scheme, referred to as CLSS-CPPA,

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

2188

IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS, VOL. 44, 2026

for V2V communication. This scheme avoided the use of
bilinear pairings and map-to-point hash functions, instead
relying on ECC and general hash functions. It supported batch
signature verification, improving computational and communication efficiency, and ensured security against various attacks
based on the ECDLP. Zhu et al. [26] proposed a certificateless conditional privacy-preserving authentication scheme for
VANETs, which was based on ECC to generate aggregate
signatures, enhancing the security of the authentication process
while preserving user privacy. However, with the advancement
of quantum computing, the security of traditional encryption
schemes has become increasingly vulnerable, as quantum
computers can potentially break widely used cryptographic
schemes, such as RSA and ECC, through techniques like
Shor’s algorithm.
This has prompted researchers to explore lattice-based cryptography, which is considered as one of the most promising
post-quantum cryptographic approaches. Wani et al. [27] proposed a lattice-based dynamic anonymous batch-verification
authentication scheme that utilized fuzzy extractors to
achieve dynamic anonymity and avoid pseudonym storage.
This scheme addressed the limitations of existing VANETs
authentication schemes in terms of quantum resistance and
storage efficiency. Nath and Choudhury [28] introduced a
lattice-based privacy-preserving mutual authentication scheme,
named LbPV, which was designed to address security and
privacy challenges in vehicle message exchanges in VANETs.
The scheme eliminated service provider monitoring, enabled
vehicles to authenticate without generating real-time parameters, and leveraged lattice-based encryption to enhance system
security. Li et al. [29] proposed a lattice-based aggregate
signature scheme with dynamic identity revocation, which
improved authentication efficiency and security while resisting
impersonation attacks in quantum computing environments.
Prajapat et al. [30] introduced a lattice-based identity-based
aggregate signature scheme that combined batch verification
and aggregate signature schemes to efficiently authenticate
multiple vehicles and aggregate their signatures. However,
the signatures generated by lattice-based cryptography tend
to be larger in size, which can result in higher communication
and computational costs, especially in resource-constrained
environments like VANETs. Moreover, most existing latticebased authentication schemes are not well-suited for vehicular
platoons, as they lack structured identity management and
support for continuous batch authentication. The tightly coupled and hierarchical nature of platoons demands low-latency
responses and dynamic identity updates.

in scenarios involving a large number of vehicles. This inefficiency becomes particularly problematic in VP, where rapid
authentication and traceability are critical for maintaining VP
reliability and security. Furthermore, the sequential nature of
re-verifying individual signatures limits the scalability of such
methods, as the computational cost increases linearly with the
number of signatures. This not only affects real-time performance but also poses challenges in scenarios where multiple
malicious entities may be involved. Shen et al. [33] proposed
a binary tree traversal method to efficiently track vehicles with
invalid signatures, thereby reducing computational overhead.
However, directly embedding signatures within the binary
tree could potentially compromise the system’s security and
privacy. Nevertheless, this approach offers an innovative perspective for advancing batch authentication research in VP.
In VP scenarios, anonymous and efficient tracing is essential
to ensure the overall security of the platoon. Traditional batch
authentication schemes are designed for general VANETs and
typically overlook the structured nature and frequent membership changes in VP. While they can authenticate vehicle
identities, they are inefficient at tracing malicious vehicles,
resulting in high computational overhead and slow response.
Therefore, our work focuses on designing a tracing mechanism
specifically optimized for the dynamic nature of VP, supporting efficient authentication while enabling rapid and scalable
tracing of malicious vehicles.

C. Malicious Vehicles Tracing for Vehicle Platoon in
VANETs
In batch authentication, when the aggregate signature verification fails, only a few scheme consider the malicious vehicles
tracing. Most approaches rely on re-verifying all signatures
to determine the source of the malicious vehicles [31], [32].
Although this scheme can effectively identify the malicious
vehicles, it incurs significant cost due to the large number of
computational and verification operations required, especially

III. S YSTEM OVERVIEW
A. System Architecture
The system architecture for LETA is shown in Fig. 1. The
infrastructure of the system consists of Trusted Authority(TA),
Trusted edge center(TEC), Roadside Unit(RSU), Vehicle Platoon(VP), and Blockchain(BC). The specific descriptions of
these entities are as follows:
1) TA: TA is a trusted authority whose communication
area forms an independent trust domain. It is responsible for
initializing the system and generating the public and private
keys for certain entities. Furthermore, the true identity of the
vehicles can only be revealed by the TA.
2) TEC: TEC is a trusted edge center with a communication area in the edge domain. It is responsible for the
authentication and access of vehicle platoons within its communication range. Additionally, it acts as a node in the
blockchain, enabling transaction retrieval and smart contract
invocation.
3) RSU: RSU is a semi-trusted entity, assumed to be
honest but curious. Deployed roadside, it connects securely
to TEC via wired links and wirelessly to vehicles, acting as a
communication bridge between the platoons and the TEC.
4) VP: VP comprises a Platoon Leader (PL) and multiple
Platoon Followers (PF). The PL is a trusted entity, typically
designated by an RSU or cloud server, elected through a
capability-based voting mechanism among vehicles, or preassigned by human operators prior to platoon formation. The
PL is responsible for managing internal coordination and
handling communication with external entities. PFs are considered semi-trusted entities, meaning that they are generally

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

LI et al.: LATTICE-BASED EFFICIENT AND PRIVACY-PRESERVING BATCH AUTHENTICATION SCHEME

2189

Fig. 1. System architecture of batch authentication for vehicle platoon in VANETs. The system model is composed of VANET infrastructure and blockchain.
The batch authentication process includes dynamic VP identity construction, hash tree-based structure generation, and aggregated signature verification. Upon
authentication failure, an anonymous efficient tracing mechanism is invoked to locate the malicious vehicle.

compliant but may occasionally exhibit misbehavior. During
system operations, they are expected to follow the instructions
issued by the PL.
5) BC: BC is a consortium blockchain maintained by
TEC, storing vehicle identity authentication data, such as
pseudonyms. This data is recorded as transactions, accessible
to all nodes. The blockchain supports user registration, information queries, and smart contract integration for automated
execution, reducing transaction delays.
Based on the infrastructure, we have designed the main
process of the system to ensure secure and efficient batch
authentication for VP in VANETs. The process is divided into
the following three steps.
1) Dynamic VP Integrated Identity Construction: This
is the foundation of VP identity authentication. First, TA
performs system initialization and generate the necessary
parameters and keys for the entire system. Following this,
each vehicle in VP dynamically generates a pseudonym and
computes the corresponding signature. The PF sends the relevant vehicle information to the PL, and the PL constructs the
VP integrated identity by designing the VPD-Tree, preventing
identity leakage, thereby protecting vehicle privacy.
2) Secure and Efficient Batch Authentication for All
Vehicles in VP: After constructing the VP integrated identity
information, the signatures of all vehicles in VP are aggregated
to generate an aggregate signature for batch authentication.
This aggregate signature is then sent through the RSU to the
TEC for verification. During this process, quantum-resistant
encryption algorithms are employed to ensure that the system remains secure in the era of quantum computing. This
approach not only effectively reduces the transmission and
storage overhead of signatures but also significantly improves
the efficiency of batch authentication.
3) Anonymous Efficient Tracing: When VP identity
authentication fails, the PL utilizes the previously constructed
VPD-Tree to quickly trace potential malicious vehicles.
Through binary search, the system can rapidly locate suspicious malicious vehicles and use ZKP to further confirm the

identity of the malicious vehicle. This process enables conditional traceability of malicious vehicles by authorized entities,
while ensuring that the privacy of legitimate participants
remains protected. It achieves an efficient tracing mechanism that discloses only the necessary identity information of
malicious vehicles, without compromising the anonymity of
legitimate participants.
B. Threat Model
According to the Dolev-Yao threat model, the system’s
threat model is defined as follows:
1) The attacker can access the data on the blockchain but
cannot tamper with it. However, they can observe and attempt
to exploit the public information to analyze the vehicle’s
historical identity, thereby compromising anonymity.
2) The attacker possesses quantum computing capabilities,
meaning they can use quantum computing to break traditional
encryption algorithms that are not resistant to quantum attacks.
3) The attacker may attempt to forge the identity of a
legitimate vehicle to join the platoon and falsify signatures
for authentication.
4) The attacker may replay historical messages, attempting
to use previously authenticated information or pseudonyms to
masquerade as a legitimate vehicle and rejoin the platoon or
communicate with the RSU.
5) PF and RSU are semi-trusted entities in the system.
These entities are generally considered honest but curious, and
they may exhibit potential malicious behavior or be subject to
attacks, meaning they cannot be fully trusted.
6) The protocol allows for some participants to be malicious.
Malicious participants may attempt to tamper with messages,
leak keys, or collaborate with attackers to carry out replay and
forgery attacks.
C. Security Requirements
The proposed scheme must satisfy the following security
requirements.

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

2190

IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS, VOL. 44, 2026

1) Privacy Preserving: The openness and dynamism of
VP risk exposing vehicle identities during communication.
To mitigate this, real identities must not be revealed during authentication, preventing attackers from deducing them
through intercepted messages.
2) Unlinkability: Attackers may attempt to infer private
information by collecting and analyzing large amounts of
messages. Therefore, it is crucial to prevent an adversary from
linking any two messages from the same vehicle.
3) Traceability: When malicious behavior occurs, effective scheme must be established to address identity tracking
issues and prevent vehicles from exploiting privacy protection
attributes. This property allows trusted authorities to trace the
real identity of malicious vehicles.
4) Non-Repudiation of Signatures: The legitimate signature
of a signer can prevent malicious adversaries from discovering
their keys. However, without valuable information, malicious
adversaries cannot generate valid aggregate signatures.
5) Quantum Resistance: This property ensures that the
system remains resistant to quantum computer-based attacks,
thus safeguarding the security of the system’s signatures,
encryption, and communication.
6) Resistance to Other Attacks: In addition to the above
properties, secure identity authentication in VP should resist
replay attacks and man-in-the-middle attacks. With the application of blockchain, the protocol should also be resistant to
birthday collisions and hijacking attacks.

TABLE I
M AIN N OTATIONS AND D ESCRIPTION

A ∈ Rqk×l is selected, where A is an element of the ring.
Then, s1 , s2 ∈ DR,s are chosen, where s1 and s2 are small
polynomial vectors of dimensions k ×1 and l ×1, respectively.
These form the secret key s = (s1 , s2 ), and the public key
component is computed as b = A · s1 + s2 mod q, generating
the public key pair (A, b). To further enhance the security of
the protocol, three one-way collision-resistant hash functions
are selected.
h0 : {0 , 1 }∗ → Rq

(1)

∗

h1 : {0 , 1 } → {v : v ∈ Rq , kv k ≤ 1 }
IV. P ROPOSED S CHEME
In this section, we will provide a detailed description
of the specific process of the LETA scheme. The scheme
consists of four steps: (1) initialization phase, where where
the TA sets the global system parameters during the initial
deployment of the vehicular network to support the subsequent authentication and tracing processes. (2) VP integrated
identity construction phase, where a vehicle requesting to
join a platoon registers with the TA to obtain a private key
and a pseudonym. The vehicle then generates a signature
and sends a request to PL, who constructs a VPD-Tree and
builds the VP-integrated identity expression for the platoon.
(3) VP identity authentication phase, where PL collects all
requests and generates an aggregate signature to perform batch
authentication of the VP identities efficiently. (4) Malicious
vehicle tracing phase, where the PL initiates a VPD-tree-based
tracing process upon detecting a failure in aggregate signature
verification, enabling efficient identification of the malicious
vehicle without compromising the anonymity of legitimate
participants. The following will provide a detailed explanation
of the proposed scheme. For better understanding, we have
included the main notations and their descriptions, as shown
in Table I.
A. Initialization Phase
First, TA selects a security parameter λ determine the
security of the lattice-based cryptosystem. A large prime
number q then chosen as the modulus for the R-LWE problem.
Next, a polynomial ring Rq = Zq [x]/hxn + 1i is defined, and

h2 : {0 , 1 }

∗

→ B∗ ,

B = {p ∈ R : kpk ≤ 2 }

(2)
(3)

Then, TA securely maintains the main secret key s and publicly sets the parameters as params = {k, q, h0 , h1 , h2 , A, b}.
B. VP Integrated Identity Construction Phase
1) Vehicle Registration: The vehicle Vi generates its real
identity identifier RVi = h0 (IDVi k NVi k s) based on the real
identity IDVi , the driver’s name NVi , and the private key s,
and submits it to the Trusted Authority (TA). Then, Vi submits
RVi to the TA. The TA randomly selects a number θVi ∈ DR,s
and creates a pseudonymous identity PVi = RVi ⊕ h0 (θVi )
based on the RVi submitted by Vi .
Meanwhile, Vi generates its private key sVi = (s1 , s2 ) using
the discrete Gaussian distribution, where each polynomial
vector in the private key pair s1 and s2 is sampled from the
discrete Gaussian distribution:
s1 = (s1,1 , s1,2 , . . . , s1,n ),

s1,i ∈ D(R, s)

(4)

s2 = (s2,1 , s2,2 , . . . , s2,n ),

s2,i ∈ D(R, s)

(5)

The private key sVi = (s1 , s2 ) is generated, and then
the public key (A, bVi ) is computed by bVi = A · s1 + s2
mod q. Vi submits the public key (A, bVi ) to the TA, which
saves the public key and binds PVi to the public key. Finally,
{PVi , (A, bVi ), T1 } is uploaded to the blockchain for storage,
where T1 is the current timestamp.
2) RSU Registration: The RSUi registration is similar to
that of vehicles, generating the corresponding pseudonymous
identity PRSUi , private key sRSUi = (s1 , s2 ) and public key

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

LI et al.: LATTICE-BASED EFFICIENT AND PRIVACY-PRESERVING BATCH AUTHENTICATION SCHEME

2191

based on the information stored in its OBU. Then, the PF sends
(HashVi , ZVi ) to the PL. The PL uses (HashVi , ZVi ) as leaf
nodes to construct a dynamic hash tree, VPD-Tree, illustrated
in Fig. 2, with the detailed process described below.
• Each leaf node contains HashVi , which represents the
integrity and identity information of vehicle Vi . After this
step, a set of leaf node hash values is obtained, denoted
as:
{HashV1 , HashV2 , . . . , HashVn }

Fig. 2. VPD-tree.

(A, bRSUi ). Finally, {PRSUi , (A, bRSUi ), T1 } is uploaded to
the blockchain for storage.
3) Signature Generation Phase: After registration, the
vehicle Vi generates a signature for the message mi ∈ {0, 1}∗
based on the input pseudonymous identity PVi , private key
sVi , and public key (A, bVi ), resulting in SignVi . The specific
process is as follows:
a) The vehicle Vi generates two random vectors zi,1 , zi,2 ∈
(Zq [x]/hxn + 1i)l , ensuring that the coefficients of each
polynomial are small, and then calculates the temporary commitment value µi :
µi = A · zi,1 + zi,2

mod q.

(6)

b) The vehicle processes the commitment value µi and
the message mi using the hash function h2 , generating the
challenge value ci for the signature:
ci = h2 (bVi k µi k mi )

(7)

c) The vehicle uses the private key sVi to calculate the
signature response values ri,1 = zi,1 + ci · s1 mod q and
ri,2 = zi,2 + ci · s2 mod q, and then generates the final
response value ri :
ri = ri,1 + A−1 · ri,2

mod q

(8)

d) The vehicle uses the commitment value µi , the response
ri , and the challenge ci as components of a zero-knowledge
proof, generating the zero-knowledge proof ZVi = (µi , ri , ci )
to prove that the signature was generated using the private key
sVi .
e) The vehicle Vi generates the signature SignVi = (ri , ci ).
f) The vehicle Vi uploads {PVi , h0 (mi ), (A, bVi ),
ri , ZVi , T2 } to the blockchain, where T2 is the current
timestamp.
4) VPD-Tree: The VP is composed of a PL and multiple
PF, with subsequent vehicles joining the vehicular network
in the form of a convoy. The PL is responsible for guiding
the convoy’s route and speed, while the PF adjusts their
driving paths and speeds based on the instructions from the
leading vehicle, thus maintaining the overall coordination of
the convoy. The process for constructing the convoy identity
is as follows:
a) Each vehicle in the convoy calculates its identity hash
value HashVi = h1 (PVi k ri k ηi k T2 ), where ηi ∈ DR,s ,

• The leaf nodes are paired up, and if there is an odd
number of nodes, empty nodes are added to pair them.
The hash value of each parent node is generated by
combining the hash values of its two child nodes. For
example, for leaf node hashes Hashlef t and Hashright ,
the parent node hash is:
Hashparent = h1 (Hashlef t k Hashright )

(9)

• The process is iterated to generate intermediate nodes,
continuing until only one top-level node remains, the root
node.
• The hash value of the root node, Root, serves as the
unique representation of the entire hierarchical hash tree,
ensuring the integrity of all leaf nodes. The Root is
then broadcast as the V P identity to all vehicles in
the platoon. When vehicles join or leave, only the partial
update of relevant values is needed to ensure the efficient
update of VP identity.
• When multiple vehicles request to join or leave the
platoon simultaneously, the corresponding branches of
the VPD-Tree can be updated independently and concurrently, rather than triggering a sequential update of the
entire structure. This is achieved by maintaining localized
subtree operations, which allow multiple update threads
or processes to perform in parallel without conflicts.
b) Vi selects a random value δi ∈ R, calculates Mi,1 =
h0 (δi ), Mi,2 = h0 (Mi,1 ||T3 ), and sends {PVi , Mi,1 , Mi,2 , T3 }
to PL, where T3 is the current timestamp.
c) After receiving the information from all vehicles, PL
0
0
recalculates Mi,2
= h0 (Mi,1 , T3 ). If Mi,2
= Mi,2 , then the
vehicle’s PVi is valid and the vehicle’s registered identity is
trusted.
d) Each vehicle in the formation negotiates and generates a
session key for subsequent internal encrypted communication
within the formation. PL first calculates the public value
BP L = A · s1 mod q and broadcasts it to all PFs. PF
calculates the public value Bi = A · s1,i mod q based on its
private key, and computes the session key Ki = BP L · s1,i
mod q. PL calculates the session key Ksession = Bi · s1
mod q. Since both parties use the same module lattice and
computation methods, it ensures the consistency of all session
keys, i.e., Ksession = Ki .
C. VP Identity Authentication Phase
1) Signature Aggregation: The PFs in the VP send their
signatures to the PL, who then aggregates the signatures of the
entire platoon. The specific aggregation process is as follows:

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

2192

IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS, VOL. 44, 2026

a) Each vehicle sends its signature Sign(Vi ) to the PL.
b) PL calculates the hash value βi for each vehicle:
h2 (α(V1 ) , t1 , µ1 , . . . , α(Vn ) , tn , µn , VP identity)
→ (β1 , β2 , . . . , βn )

(10)

c) PL aggregates the challenge values ci from all vehicles
(V1 , V2 , V3 , . . . , Vn ) to generate cagg :
cagg =

n
X

βi · ci

mod q

(11)

i=1

d) The responses ri from all vehicles (V1 , V2 , V3 , . . . , Vn )
are aggregated to generate ragg :
ragg =

n
X

βi · ri

mod q

(12)

i=1

e) Generate the aggregated signature AggSign = (ragg , cagg ).
f) The VP uses RSUi as a relay device to send
{VP identity, AggSign , T5 } to the corresponding TEC, where
T5 is the timestamp when the aggregated signature is generated.
2) Signature Verification: After receiving the aggregated
signature AggSign sent by the RSU, the TEC will verify the
signature. The specific verification process is as follows:
a) The RSUi first verifies the timestamp T5 . If T − T5 >
∆T , it is considered a malicious signature, and the RSU will
reject the message. If T5 is within the allowed time range,
the message is considered valid, and the subsequent signature
verification can proceed.
b) Recalculate each vehicle’s hash value βi according to
Eq. 10.
c) Verify whether the following equation holds:
A · ragg =

n
X

βi · (µi + ci · bVi )

mod q

(13)

i=1

If Eq. 13 does not hold, it indicates the presence of malicious
vehicles in the convoy. If Eq. 13 holds, the verification process
accepts the correctness of the aggregated signature.
D. Malicious Vehicle Tracing Phase
When aggregated signature verification fails, it indicates
the presence of malicious vehicles in the platoon, requiring a
trace-back mechanism to identify and revoke their identities.
Following Algorithm 1, the VPD-Tree employs a hierarchical
structure that organizes vehicles across multiple levels, where
the root node represents the entire platoon and the leaf
nodes correspond to individual vehicles. The malicious vehicle tracing mechanism leverages this structure to efficiently
locate suspected vehicles and utilizes ZKP embedded in the
leaf nodes to verify identities without disclosing confidential
information, thereby enabling anonymous and efficient tracing
within the VP.
1) Starting from the root node, dynamically calculate the
hash value as Root0 = h1 (Hashlef t ||Hashright ). If
the calculated Root0 is not equal to the original Root,
proceed to the child nodes for further examination.

Algorithm 1 Efficient Malicious Vehicles Tracing
Input: Vehicle platoon information based on V P D − T ree
Output: ZKP for malicious vehicles
for VPD-Tree do
if The children of the Root is N ull and verity ZKP =
F alse then
return ZKP ;
else
Root0 = h1 (Hashlef t ||Hashright );
if Root0 ! = Root then
if Children0lef t ! = Childrenlef t then
errorT ree = error(Childrenlef t );
end if
if Children0right ! = Childrenright then
errorT ree = error(Childrenright );
end if
end if
return leaf nodes;
end if
end for
Find the suspicious leaf nodes;
Verify the ZKP of the suspicious leaf nodes;
if V erif yZKP (Leaf N ode.ZKP ) == F alse then
Mark the leaf as malicious;
end if
return the ZKP for malicious vehicles;

2) For each child node, dynamically recalculate its hash
value and compare Hash0 with Hash. If the values do
not match, continue to examine its child nodes. If they
match, it indicates that this subtree is valid, and that
branch can be excluded from further investigation.
3) Recursively trace down to the leaf node layer, ultimately
locating the smallest problematic subtree. This tracing
process can be performed in parallel across disjoint
branches, significantly improving efficiency in largescale platoon environments.
4) After locating the smallest problematic subtree, the
authenticity of the node’s data is verified through the
zero-knowledge proof ZVi = (µi , ri , ci ). In the context
of the VPD-Tree, each leaf node stores the ZKP of
the corresponding vehicle, enabling privacy-preserving
identity verification without exposing sensitive identity
information. First, the commitment value µ0i is recalculated as:
µ0i = A · ri − ci · bVi

mod q

(14)

Next, the consistency of the commitment value is
checked. If µi 6= µ0i , the node is immediately flagged
as a potential malicious node. If µi = µ0i , the challenge
value c0i is calculated as:
c0i = h2 (bVi k µi k m)

(15)

If ci = c0i , the node is considered legitimate; otherwise,
it is marked as a malicious node.
5) The PL identifies the pseudonym of the malicious vehicle through the blockchain and submits it to the TA

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

LI et al.: LATTICE-BASED EFFICIENT AND PRIVACY-PRESERVING BATCH AUTHENTICATION SCHEME

2193

Fig. 3. Overall process workflow of LETA.

without accessing the vehicle’s real identity. The TA, as
the only entity capable of resolving pseudonyms to real
identities, performs the identity revocation, updates the
platoon records, and securely broadcasts the necessary
changes to nearby vehicles and RSUs.
6) To prevent identity link attacks and protect vehicle
privacy, the TA will update the pseudonyms of vehicles
and RSUs after a certain period of time. The TA will
0
∈ DR,s , and
re-select random numbers θV0 i and θRSU
i
regenerate the pseudonyms as follows:
P0Vi = RVi ⊕ h0 (θV0 i ),
0
0
PRSU
= RRSUi ⊕ h0 (θRSU
).
i
i

(16)
(17)

The TA will issue new pseudonyms to vehicles and
RSUs for identity updates. The smart contract will
0
replace the original pseudonyms PV0 i and PRSU
on the
i
blockchain The PL will update the relevant leaf nodes
in the VPD-Tree.
The overall flow diagram of our proposed framework is
illustrated in Fig.3.
V. S ECURITY A NALYSIS
A. Proof of Correctness
In this section, we will discuss the correctness proof of
the final aggregated signature and verify the reliability of the
aggregated signature AggSign . The correctness of the aggregated signature is shown as follows:
A · ragg
n
X
=A·
βi · ri mod q
i=1

=A·
=A·

n
X

βi ri,1 + A−1 ri,2



mod q

i=1
n
X


(βi (zi,1 + ci · s1 ) + A−1 βi (zi,2 + ci · s2 ) mod q

i=1

=A·

n
X

βi (zi,1 + ci · s1 ) +

i=1

=
=
=

n
X
i=1
n
X
i=1
n
X

n
X

βi (zi,2 + ci · s2 ) mod q

i=1

βi (A · zi,1 + A · ci · s1 + zi,2 + ci · s2 ) mod q
βi · (µi + ci · (A · s1 + s2 )) mod q
βi · (µi + ci · bVi ) mod q

i=1

B. Formal Analysis
In this chapter, we analyze the unforgeability of the aggregated signature under the Q-Random Oracle Model (Q-ROM)
[34], demonstrating that attackers cannot forge a valid signature in the proposed protocol. Q-ROM, an extension of
the traditional Random Oracle Model (ROM), accommodates quantum environments by enabling quantum parallel
queries. The protocol’s security, based on the R-LWE assumption, ensures resistance to quantum attacks. Using the game
sequence technique [35], we formally prove the protocol’s
post-quantum security by modeling interactions between quantum polynomial-time adversaries and challengers through a
response-challenge game. The key components of Q-ROM are
outlined below.

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

2194

IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS, VOL. 44, 2026

Definition 1 (Participants and Partnering): Participants
consist of TA, TEC, PL, and PF. In the i-th instance, the
participants are represented as ΨiT Ai , ΨiT ECi , ΨiP Li , and
ΨiP Fi , respectively. During the protocol execution, TEC, PL,
and PF share the same global public key A and use a consistent
signature verification mechanism to validate the legitimacy of
signatures. Thus, TEC, PL, and PF form a partnership.
Definition 2 (Queries): Queries simulate the capabilities of
the attacker.
Execute (ΨiT Ai , ΨiT ECi , ΨiP Li , ΨiP Fi ): The attacker passively records all interactions among vehicles, RSUs, and TEC
during protocol execution.
Send (ΨiT Ai , ΨiT ECi , ΨiP Li , ΨiP Fi , Aggsign): A forges and
sends a counterfeit aggregated signature Aggsign∗ to ΨiT ECi .
If Aggsign∗ is successfully verified, ΨiT ECi responds to A.
Reveal (ΨiT Ai , ΨiT ECi , ΨiP Li , ΨiP Fi ): This query simulates
key leakage to the attacker. If the correct aggregated signature
cannot be generated, it indicates no key leakage.
Corrupt (ΨiP Li , ΨiP Fi ): This query simulates the attacker
gaining full control over a vehicle’s internal state and accessing all its stored information.
Test (ΨiT ECi , ΨiP Li , ΨiP Fi ): This query simulates an
adversary’s attack on the protocol’s unforgeability. The
attacker selects a signature, and the challenger randomly
returns either a genuine or forged aggregated signature, which
the attacker must distinguish.
Definition 3 (Freshness): An instance is considered fresh
if it satisfies the following conditions: 1) The submitted
aggregated signature is confirmed to have been computed by
the instance ΨiP Li ; 2) The attacker has not performed a Reveal
query on ΨiP Li or its partners. If these conditions are met, the
instance is deemed fresh.
Definition 4 (Semantic Security): Within quantum polynomial time, the attacker is allowed to perform at most
one Test(ΨiT ECi , ΨiP Li , ΨiP Fi ) query and multiple other
queries to determine the correctness of the return value from
Test(ΨiT ECi , ΨiP Li , ΨiP Fi ). Specifically, the attacker guesses
the aggregated signature in the Test query and outputs a
guessed value. The advantage of the attacker is defined as:

Proof: Suppose adversary A can forge the aggregated signature. In this case, challenger B can leverage the query behavior
of adversary A to extract the solution to the R-LWE problem.
A series of security games is used to complete the formal
security proof, where Win i denotes challenger B’s success in
completing Game i .
Game0 : Adversary A fully simulates the real behavior of the
signature system without any additional interference. Based on
the definition of semantic security, we can derive:

AdvA
P = |2 · Pr[suc(A)] − 1|.

(18)

where AdvA
P < η indicates that the protocol is secure, and η
is sufficiently small.
Lemma 1 (Difference Lemma [36]): Let X, Y, Z represent
events in a probability space, and suppose the event Y ∧¬Z is
equivalent to the event X ∧¬Z. Then, Pr[X]−Pr[Y ] ≤ Pr[Z].
Theorem 1: In the Q-ROM model, define Adv A as the
probability that an adversary A1 forges a valid aggregated
signature within a finite time t. Suppose the adversary A
makes q0 queries to h0 , q1 queries to h1 , q2 queries to
h2 , qsk private key s queries, and qs signing Sign queries.
The advantage of the adversary A in forging an aggregated
signature is bounded by:
√
2 q2
qs + qsk
q3 + q3
+ 2Adv R−LWE
(19)
Adv A ≤ 0 n 1 + λ/2 +
A
2
2λ−1
2
where Adv R−LWE
is the probability of solving the R-LWE
A
problem.

Adv A = |2 · Pr[Win 0 ] − 1| .

(20)

Game1 : Challenger B replaces the hash functions h0 , h1 ,
and h2 with random oracles (RO1 , RO2 , RO3 ) and simulates
the behavior of these oracles. In the Q-ROM, since adversary
A cannot distinguish between the real hash functions and the
random oracles, it cannot differentiate this game from the
actual execution of the protocol. Therefore:
|Pr[Win 1 ] − Pr[Win 0 ]| = 0.

(21)

Game2 : Similar to Game1 , h0 and h1 queries are simulated.
If adversary A’s queries to h0 or h1 result in a collision (i.e.,
two different inputs produce the same hash output), the game
terminates immediately. Based on the birthday paradox, we
can derive:
q13
q03
+ n+1
.
(22)
|Pr[Win 2 ] − Pr[Win 1 ]| ≤ n+1
2
2
Game3 : Adversary A forges a valid signature Sign Vi =
(ri , ci ) without relying on the private key sVi . The adversary
uses queries to h2 to forge a specific challenge value ci that
satisfies the signature verification condition. After obtaining
µi and ci , the attacker attempts to forge the response value ri
to make the verification equation hold.
To succeed, the attacker must find a valid ci through h2
queries. Given that the adversary can perform q2 queries,
√
the maximum success probability for forging is q2 /2λ/2 .
Therefore, we have:
√
q2
|Pr[Win 3 ] − Pr[Win 2 ]| ≤ λ/2 .
(23)
2
Game4 : Challenger B simulates the process of generating
the aggregated signature. Adversary A can make up to qs
signing queries on messages {m1 , m2 , . . . , mn } and attempts
to forge a valid aggregated signature, where at least one
individual signature Sign i was not included in the signing
queries. The maximum success probability for adversary A
forging a correct aggregated signature is qs /2λ . Therefore, we
have:
qs
(24)
|Pr[Win 4 ] − Pr[Win 3 ]| ≤ λ .
2
Game5 : Challenger B replaces the original private key
sVi = (s1 , s2 ) with a random key s∗Vi = (s01 , s02 ). Based
on the R-LWE assumption, s∗Vi = (s01 , s02 ) is computationally
indistinguishable from sVi = (s1 , s2 ). During the signature
generation simulation, all computations involving the original
private key are replaced with computations based on the
random key s∗Vi .
If adversary A attempts to approximate the real private key
through private key queries, the maximum probability of success after qsk queries is qsk /2λ . On the other hand, if adversary

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

LI et al.: LATTICE-BASED EFFICIENT AND PRIVACY-PRESERVING BATCH AUTHENTICATION SCHEME

TABLE II
C OMPARISON OF S ECURITY F EATURES

A successfully computes sVi = (s1 , s2 ),where s2 = b − As1 ,
the success probability is bounded by Adv R−LWE
, which is
A
the advantage of solving the R-LWE problem. Therefore, we
have:
|Pr[Win 5 ] − Pr[Win 4 ]| ≤ Adv R−LWE
+
A

qsk
.
2λ

(25)

In fact, if adversary A fails to make any random oracle
queries with the correct input during the game, A gains no
advantage in distinguishing the real private key sVi from a fake
key of the same length created using random values. Therefore,
Pr[Win 5 ] = 1/2. We can further derive:
Adv A
= |2 Pr[Win 0 ] − 1|
= 2 Pr[Win 5 ] − 1 + 2(Pr[Win 0 ] − Pr[Win 5 ])
≤ 2 |Pr[Win 0 ]−Pr[Win 1 ]|+· · ·+2 |Pr[Win 4 ]−Pr[Win 5 ]|
√
2 q2
q3 + q3
qs + qsk
+ 2Adv R−LWE
.
(26)
≤ 0 n 1 + λ/2 +
A
2
2λ−1
2
This result demonstrates that the aggregated signature protocol possesses unforgeability.

C. Other Security Analysis
We compared LETA with the schemes [30], [37], [38], and
[39] to evaluate their security features. Scheme [37] cannot
resist impersonation attacks or quantum attacks and fails
to ensure unlinkability and anonymous traceability. Scheme
[38] fails to provide anonymous traceability and quantum
resistance. Scheme [39] cannot resist replay attacks and impersonation attacks and also lacks unlinkability and anonymous
traceability. Scheme [30] fails to resist replay attacks and
impersonation attacks. A detailed comparison of security features is shown in the table, where “X” indicates that the
scheme satisfies the corresponding security feature, and “ ”
indicates that it does not. The results show that Table II,
compared to other related schemes, the proposed authentication scheme offers more comprehensive support for security
features. Therefore, LETA provides higher security and more
reliable protection for VP.
Next, a detailed analysis of the security features in Table II
will be presented.

%

2195

1) Conditional Privacy Protection: To prevent unauthorized identity access, pseudonyms are generated for vehicles
and RSUs in VANETs. PVi and PRSUi represent the
pseudonyms of vehicles and RSUs, respectively. These
pseudonyms are issued by the TA during their respective
registration phases. The TA is the sole entity with access to
true identities, ensuring the pseudonyms cannot reveal real
identities.
2) Unlinkability: In the proposed scheme, vehicle
pseudonyms are generated as PVi = RVi ⊕ h0 (θVi ), where h0
is a one-way collision-resistant hash function. Pseudonyms
are dynamic, and the platoon is constructed using a dynamic
hash tree with random values to enhance unlinkability. Thus,
no one can link pseudonyms or platoon data to a vehicle’s
real identity.
3) Message Authentication and Integrity: To ensure identity
authentication and message integrity, each message is signed
and aggregated by the registered vehicles before being sent
to the TEC. The TEC can then verify the validity of the
aggregated signature. A formal proof that the aggregated
signature cannot be maliciously forged has been provided
above.
4) Anonymous Traceability: The identities and signatures
of platoon vehicles are mapped to the VPD-Tree. In the event
of a platoon identity authentication failure, the VPD-Tree
can be used to quickly locate the malicious vehicle. ZKP is
then employed to verify the malicious vehicle, ensuring its
identification while preserving the privacy of the VP.
5) Non-Repudiation: The unforgeability of the aggregated
signature ensures that the VP cannot deny sending a message.
Upon detecting malicious behavior, the verifier can link the
signature to a specific VP and, using the VPD-Tree and the TA,
identify the malicious vehicle. Thus, the protocol guarantees
non-repudiation.
6) Resistance to Quantum Attacks: RSA is a public-key
cryptosystem based on the integer factorization problem, while
ECC is based on the discrete logarithm problem. However,
these problems can be efficiently solved in a quantum computing environment. As a result, lattice-based cryptography
has gained significant attention as a means to resist quantum
attacks. The proposed aggregated signature protocol is built
on the R-LWE problem, and its security relies on the computational complexity of this problem. Since quantum computers
cannot efficiently solve the R-LWE problem, the protocol
remains secure in a quantum computing environment.
7) Resistance to Other Security Attacks:
a) Man-in-the-middle attack: The VP performs identity authentication through signature verification, ensuring
the legitimacy of each vehicle’s identity within the platoon.
Therefore, the proposed protocol is resistant to man-in-themiddle attacks.
b) Replay attack: Each message includes a timestamp to
prevent replay attacks. The verifier first checks the timestamp
to ensure the freshness of the message. Thus, the proposed
protocol is resistant to replay attacks.
c) Forgery attack: The signature algorithm used in the
protocol ensures message integrity. Any modification of the

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

2196

IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS, VOL. 44, 2026

TABLE III
C OMPARISON OF C OMMUNICATION C OST

data will cause the verification equation to fail. Hence, the
protocol is resistant to forgery attacks.
d) Impersonation attack: In the proposed protocol, correctness, unforgeability, and authenticity ensure that signatures
generated using false identities cannot pass signature verification.
VI. P ERFORMANCE A NALYSIS
To prove the efficiency of LETA, we conducted simulation
experiments to evaluate the computational and communication
cost of identity authentication. Additionally, we also analyze
the efficiency of tracking malicious vehicles to highlight the
performance of our tracking scheme. All experiments were
implemented in Python and executed on a device running
macOS with an M3 chip, featuring an 8-core CPU and a
10-core GPU. In the VP batch authentication experiments, the
LETA scheme was compared with the following schemes:
SAS [39]: Wang and Wu designed an efficient lattice-based
sequential aggregate signature scheme.
LBAS [29]: Li et al. proposed a lattice-based batch
authentication scheme with dynamic identity revocation,
which enhances verification efficiency and supports quantumresistant security for VANETs.
IBAGS [30]: Prajapat et al. proposed a novel lattice-based
identity-based aggregate signature system. This approach combines batch verification and aggregate signature mechanisms
to authenticate multiple vehicle units and aggregate multiple
user signatures into a single signature.
ES-DA-LBCLA [27]: Wani et al. proposed a lattice-based
dynamic anonymous batch-verifiable authentication scheme
for VANETs, which resists quantum attacks and eliminates
pseudonym storage by using a fuzzy extractor for dynamic
anonymity.
A. Analysis of Communication Cost
To evaluate the communication cost of our proposed
scheme, the hash length(Lh ) is set to 20 bytes, and q is set to
32 bytes. To ensure the same security level, Rq is set to 32
bytes and Rp is set to 48 bytes. Additionally, for comparison
with other schemes, the parameters are configured with G1
set to 128 bytes, G to 20 bytes, and Zq∗ to 40 bytes. In
our proposed scheme, the signature consists of (ri , ci ), so the
message length sent to the TEC is |Rq | × dlog2 P e + Lh = 180
bytes.
Similarly, we calculated the communication costs of the
SAS, LBAs, IBAGS and ES-DA-LBCLA schemes, and the
results are presented in Table III. Lattice-based cryptography uses higher-dimensional mathematical structures to resist

Fig. 4. Comparison of communication costs for different VP vehicle counts.

quantum attacks, resulting in larger ciphertexts and signatures
compared to traditional cryptography. Consequently, achieving
quantum resistance comes with a slight increase in communication cost in our proposed protocol. However, because the
modular lattice are used, LETA can provide stronger security
with smaller parameters, so the communication cost of the proposed scheme is lower than that of other lattice-based schemes.
To provide a more intuitive comparison of the differences
between these schemes, we evaluated the communication cost
under different numbers of vehicles, with the results shown
in the Fig. 4. The analysis indicates that in single signature
scenarios, our scheme achieves the lowest communication
cost. Given that n increases, the communication cost of LETA
remains the lowest compared to SAS, LBAs, IBAGS and
ES-DA-LBCLA. Overall, compared to the aforementioned
schemes, our proposed scheme consistently exhibits the lowest
communication cost in all scenarios, highlighting its advantages in resource utilization and efficiency.
Overall, our scheme achieves lower communication costs
compared to others, highlighting its efficiency and resource
utilization, especially in VANETs. It minimizes data transmission while maintaining security, ensuring effective operation
in resource-limited environments.
B. Analysis of Computation Cost
In this section, we present a detailed comparison of the
computational costs of the proposed scheme with the existing
aggregate signature schemes SAS, LBAs, IBAGS and ESDA-LBCLA. The computational cost evaluation is based on
the execution time of core cryptographic operations, including bilinear pairing, polynomial addition/multiplication, and
hashing, as detailed in Table IV.
Our scheme includes detailed steps for signature generation
and verification, with the execution time for each step listed
in Table V. Specifically, the time required for generating a
single signature is 4Ta + 3Tm + Th ≈ 5.5328ms. During
the signature verification phase, our scheme requires the least
amount of time compared to other schemes, mainly due to the
use of public key verification, which simplifies the relevant
operations and reduces computational complexity.
Fig. 5(a) shows the computational cost of signature generation for different schemes, Fig. 5(b) shows the computational
cost of signature verification for different schemes, and

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

LI et al.: LATTICE-BASED EFFICIENT AND PRIVACY-PRESERVING BATCH AUTHENTICATION SCHEME

2197

Fig. 5. Comparison of computational cost at different stages.

TABLE IV
R ELATED O PERATION T IME

Fig. 5(c) shows the total cost of identity authentication for
these schemes. The results indicate that, compared to the
SAS and ES-DA-LBCLA schemes, our scheme significantly
reduces the computational cost at each step, demonstrating its
advantage in minimizing resource consumption. Compared to
the LBAS and IBAGS schemes, our solution maintains higher
security and efficiency while slightly lowering computational
costs. The improved computational efficiency can be largely
ascribed to the fact that both the signature generation and verification procedures in the proposed scheme are based solely
on lightweight polynomial addition and multiplication operations. These operations are inherently efficient and impose
minimal computational burden, which contributes to reduced
latency and lower resource consumption. The reduction in
computational cost not only benefits real-time authentication
but also helps conserve system resources, making the scheme
particularly suitable for VANETs.
C. Malicious Vehicle Tracing Efficiency Analysis
In this section, we evaluate the performance of the proposed
scheme in tracing malicious vehicles. The time complexity
of tracing using the VPD-Tree is O(log n), whereas the time
complexity of directly traversing and verifying all vehicles is
O(n). This clearly demonstrates that our proposed method is
significantly more efficient than traditional schemes, especially
in large-scale scenarios.
To further validate this advantage, we conduct an ablation
experiment comparing the tracing time of the VPD-Tree and
the sequential re-authentication mechanism under different
platoon sizes with 5% and 10% malicious vehicles, as shown
in Fig. 6(a) and Fig. 6(b). The results show that the VPD-Tree
consistently achieves lower tracing time, with the performance
gap widening as the platoon size increases, confirming its

Fig. 6. (a) Tracing time with 5% malicious vehicles (b) Tracing time with
10% malicious vehicles.

superior scalability and efficiency in high-mobility VP environments.
Specifically, in the experiments, the number of vehicles was
set from 20 to 100, and the proportion of malicious vehicles
was set at 5%, 10%, 15%, and 20%. To ensure the accuracy
of the results, each scenario was tested five times, and the
average was calculated. The Fig. 7 shows the malicious vehicle
traceability based on VPD-Tree.
We increased the proportion of malicious vehicles step
by step, using 1% as the baseline, to analyze the growth
of malicious vehicle tracing cost, as shown in Fig. 7(a).
The tracking cost growth ratio is calculated as the ratio
of time0 /time, where time0 is the time required for the
comparison experiment, and time is the time required for the
baseline. The results show that, in VP with different numbers

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

2198

IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS, VOL. 44, 2026

TABLE V
C OMPARISON OF C OMPUTATION C OST

Fig. 7. Malicious vehicle tracing based on VPD-tree.

of vehicles, the increase in tracing costs is relatively small
as the proportion of malicious vehicles increases. Even when
the number of vehicles reaches 100, a 20-times increase in
malicious vehicles leads to an increase in tracing cost of less
than 5 times. Fig. 7(b) shows the trend of tracing cost as
the number of vehicles increases, with 10 vehicles as the
baseline. It can be seen that when the number of vehicles
in the VP increases by a factor of 10, the traceability cost
increases by about 8 times. This is mainly due to the increase
in the number of layers in the VPD-Tree as the number of
vehicles grows, leading to a significant increase in traceability
cost, but the overall efficiency remains high. Fig. 7(c) shows
that, even when there are 20% malicious vehicles in a VP
of 100 vehicles, the traceability time is only about 35 µs,
further substantiating the efficiency of our malicious vehicle
traceability scheme.
In conclusion, the experimental results demonstrate that
the proposed scheme exhibits excellent efficiency in tracing
malicious vehicles, providing a highly scalable and effective
solution.
The experimental results show that our scheme enables
efficient platoon identity authentication and malicious vehicle
tracing. However, due to the use of lattice-based cryptography,
integration with existing VANETs infrastructure may be challenging. To address this, a hybrid cryptographic architecture
and hardware acceleration, FPGA-based implementations, can
be adopted to improve compatibility and practical deployment.

hash tree and vehicle pseudonyms to preserve privacy. The
VPD-tree and modular lattice are utilized to construct the
aggregate signature for secure and efficient batch authentication of VP. Moreover, ZKP is applied on the VPD-tree
to trace the malicious vehicles of VP effectively. Formal
security analysis and performance experiments are conducted
to demonstrate that LETA performs higher security to resist
quantum attacks through lattice-based signatures, and takes
lower computation and communication costs for the novel
VPD-tree structure and efficient batch authentication scheme.
In future work, we will address VP identity authentication
in cross-trust-domain scenarios to enhance the secure sharing
of parameters and the efficiency of group authentication.
Furthermore, by offloading part of the computation to RSUs or
MECs, we aim to enable vehicles with limited computational
capabilities to meet the requirements of lattice-based cryptography, while simultaneously improving the scalability of the
tracing mechanism to achieve load balancing and low-latency
performance.
R EFERENCES
[1]

[2]

[3]

VII. C ONCLUSION
In this paper, we propose LETA, a lattice-based efficient
and traceable privacy-preserving batch authentication scheme
for vehicle platoon in VANETs. The scheme constructs the
dynamic VP integrated identity structure VPD-Tree based on

[4]

S. Sivanandham and M. S. Gajanand, “Platooning for sustainable freight
transportation: An adoptable practice in the near future?,” Transp. Rev.,
vol. 40, no. 5, pp. 581–606, Sep. 2020.
W. Li, C. Meese, H. Guo, and M. Nejad, “Aggregated zero-knowledge
proof and blockchain-empowered authentication for autonomous
truck platooning,” IEEE Trans. Intell. Transp. Syst., vol. 24, no. 9,
pp. 9309–9323, Sep. 2023.
F.-E. Braiteh, F. Bassi, and R. Khatoun, “Platooning in connected
vehicles: A review of current solutions, standardization activities, cybersecurity, and research opportunities,” IEEE Trans. Intell. Vehicles,
vol. 10, no. 5, pp. 1–23, May 2025.
R. A. Biroon, Z. A. Biron, and P. Pisu, “False data injection attack
in a platoon of CACC: Real-time detection and isolation with a
PDE approach,” IEEE Trans. Intell. Transp. Syst., vol. 23, no. 7,
pp. 8692–8703, Jul. 2022.

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

LI et al.: LATTICE-BASED EFFICIENT AND PRIVACY-PRESERVING BATCH AUTHENTICATION SCHEME

[5]

Y. Xia, S. Zhu, X. Liu, and Q. Zhong, “EPP-GAS: An efficient and
privacy-preserving cross trust-domain group authentication scheme for
vehicle platoon based on blockchain,” IEEE Trans. Intell. Transp. Syst.,
vol. 25, no. 12, pp. 19744–19756, Dec. 2024.
[6] S. Yu et al., “Efficient ECC-based conditional privacy-preserving aggregation signature scheme in V2V,” IEEE Trans. Veh. Technol., vol. 72,
no. 11, pp. 15028–15039, Nov. 2023.
[7] Z. Xu, D. He, N. Kumar, and K.-K.-R. Choo, “Efficient certificateless
aggregate signature scheme for performing secure routing in VANETs,”
Secur. Commun. Netw., vol. 2020, pp. 1–12, Feb. 2020.
[8] Q. Mei, H. Xiong, J. Chen, M. Yang, S. Kumari, and M. K. Khan,
“Efficient certificateless aggregate signature with conditional privacy
preservation in IoV,” IEEE Syst. J., vol. 15, no. 1, pp. 245–256, Mar.
2021.
[9] G. Thumbur, G. S. Rao, P. V. Reddy, N. B. Gayathri, D. V. R. K. Reddy,
and M. Padmavathamma, “Efficient and secure certificateless aggregate
signature-based authentication scheme for vehicular ad hoc networks,”
IEEE Internet Things J., vol. 8, no. 3, pp. 1908–1920, Feb. 2021.
[10] S. K. Dwivedi, R. Amin, S. Vollala, and A. K. Das, “Design of
blockchain and ECC-based robust and efficient batch authentication
protocol for vehicular ad-hoc networks,” IEEE Trans. Intell. Transp.
Syst., vol. 25, no. 1, pp. 275–288, Jan. 2024.
[11] H. J. Nath and H. Choudhury, “A privacy-preserving mutual authentication scheme for group communication in VANET,” Comput.
Commun., vol. 192, pp. 357–372, Aug. 2022. [Online]. Available:
https://www.sciencedirect.com/science/article/pii/S0140366422002262
[12] S. Kumari, M. Singh, R. Singh, and H. Tewari, “A post-quantum lattice based lightweight authentication and code-based hybrid encryption
scheme for IoT devices,” Comput. Netw., vol. 217, Nov. 2022, Art.
no. 109327. [Online]. Available: https://www.sciencedirect.com/science/
article/pii/S138912862200367X
[13] H. Khalid, S. Jahari Hashim, F. Hashim, W. Ameen Mahmoud AlJawher, M. Akmal Chaudhary, and H. H. M. Altarturi, “RAVEN: Robust
anonymous vehicular end-to-end encryption and efficient mutual authentication for post-quantum intelligent transportation systems,” IEEE
Trans. Intell. Transp. Syst., vol. 25, no. 11, pp. 17574–17586, Nov.
2024.
[14] S. Zhang, X. Du, and X. Liu, “A novel and quantum-resistant handover
authentication protocol in IoT environment,” Wireless Netw., vol. 29,
no. 6, pp. 2873–2890, Aug. 2023.
[15] X. Li, L. Zhou, X. Yin, and J. Ning, “A security-enhanced certificateless designated verifier aggregate signature scheme for HWMSNs
in the YOSO model,” IEEE Internet Things J., vol. 11, no. 6,
pp. 10865–10879, Mar. 2024.
[16] T. Li, J. Zhang, Y. Shen, and J. Ma, “Hierarchical and multi-group data
sharing for cloud-assisted industrial Internet of Things,” IEEE Trans.
Services Comput., vol. 16, no. 5, pp. 3425–3438, Sep. 2023.
[17] M. Asghar, R. R. M. Doss, and L. Pan, “A scalable and efficient
PKI based authentication protocol for VANETs,” in Proc. 28th Int.
Telecommun. Netw. Appl. Conf. (ITNAC), Nov. 2018, pp. 1–3.
[18] J. Cui, J. Zhang, H. Zhong, and Y. Xu, “SPACF: A secure privacypreserving authentication scheme for VANET with cuckoo filter,” IEEE
Trans. Veh. Technol., vol. 66, no. 11, pp. 10283–10295, Nov. 2017.
[19] C. Zhang et al., “TPPR: A trust-based and privacy-preserving platoon
recommendation scheme in VANET,” IEEE Trans. Services Comput.,
vol. 15, no. 2, pp. 806–818, Mar. 2022.
[20] K. A. Yadav and P. Vijayakumar, “LPPSA: An efficient lightweight
privacy-preserving signature-based authentication protocol for a vehicular ad hoc network,” Ann. Telecommun., vol. 77, nos. 7–8, pp. 473–489,
Aug. 2022.
[21] B. Chen, Z. Wang, T. Xiang, J. Yang, D. He, and K.-K.-R. Choo,
“BCGS: Blockchain-assisted privacy-preserving cross-domain authentication for VANETs,” Veh. Commun., vol. 41, Jun. 2023, Art. no. 100602.
[22] H. Du, Q. Wen, S. Zhang, and M. Gao, “An improved conditional
privacy protection scheme based on ring signcryption for VANETs,”
IEEE Internet Things J., vol. 10, no. 20, pp. 17881–17892, Oct. 2023.
[23] D. Boneh, C. Gentry, B. Lynn, and H. Shacham, “Aggregate and
verifiably encrypted signatures from bilinear maps,” in Proc. Int. Conf.
Theory Appl. Cryptograph. Techn., 2003, pp. 416–432.
[24] J. Zhang, Q. Zhang, X. Lu, and Y. Gan, “A novel privacypreserving authentication protocol using bilinear pairings for the VANET
environment,” Wireless Commun. Mobile Comput., vol. 2021, no. 1, Jan.
2021, Art. no. 6692568.
[25] I. Ali, Y. Chen, N. Ullah, R. Kumar, and W. He, “An efficient and
provably secure ECC-based conditional privacy-preserving authentication for vehicle-to-vehicle communication in VANETs,” IEEE Trans.
Veh. Technol., vol. 70, no. 2, pp. 1278–1291, Feb. 2021.

2199

[26] F. Zhu, X. Yi, A. Abuadbba, I. Khalil, X. Huang, and F. Xu, “A securityenhanced certificateless conditional privacy-preserving authentication
scheme for vehicular ad hoc networks,” IEEE Trans. Intell. Transp. Syst.,
vol. 24, no. 10, pp. 10456–10466, Oct. 2023.
[27] N. Majeed Wani, G. Kumar Verma, and V. Chamola, “Dynamic
anonymous quantum-secure batch-verifiable authentication scheme
for VANET,” IEEE Trans. Consum. Electron., vol. 70, no. 4,
pp. 7112–7120, Nov. 2024.
[28] H. J. Nath and H. Choudhury, “LbPV: Lattice-based privacy-preserving
mutual authentication scheme for VANET,” Comput. Electr. Eng.,
vol. 120, Dec. 2024, Art. no. 109765.
[29] F. Li, Y. Cui, J. Wang, H. Zhou, X. Wang, and Q. Yang, “Latticebased batch authentication scheme with dynamic identity revocation in
VANET,” Int. J. Intell. Syst., vol. 37, no. 11, pp. 9442–9460, Nov. 2022.
[30] S. Prajapat et al., “Secure lattice-based aggregate signature scheme for
vehicular ad hoc networks,” IEEE Trans. Veh. Technol., vol. 73, no. 9,
pp. 12370–12384, Sep. 2024.
[31] X. Yang, H. Wen, R. Diao, X. Du, and C. Wang, “Improved security of
a pairing-free certificateless aggregate signature in healthcare wireless
medical sensor networks,” IEEE Internet Things J., vol. 10, no. 12,
pp. 10881–10892, Dec. 2023.
[32] M. Azees, P. Vijayakumar, and L. J. Deboarh, “EAAP: Efficient anonymous authentication with conditional privacy-preserving scheme for
vehicular ad hoc networks,” IEEE Trans. Intell. Transp. Syst., vol. 18,
no. 9, pp. 2467–2476, Sep. 2017.
[33] G. Shen, C. Xia, Y. Li, H. Shen, W. Meng, and M. Zhang, “Traceable
and privacy-preserving authentication scheme for energy trading in V2G
networks,” IEEE Internet Things J., vol. 11, no. 4, pp. 6664–6676, Feb.
2024.
[34] A. A. Al-Saggaf, T. Sheltami, H. Alkhzaimi, and G. Ahmed,
“Lightweight two-factor-based user authentication protocol for IoTenabled healthcare ecosystem in quantum computing,” Arabian J. Sci.
Eng., vol. 48, no. 2, pp. 2347–2357, Feb. 2023.
[35] M. Hhan, K. Xagawa, and T. Yamakawa, “Quantum random oracle
model with auxiliary input,” in Proc. Int. Conf. Theory Appl. Cryptol.
Inf. Secur., vol. 2019, 2019, pp. 584–614.
[36] D. Pointcheval and J. Stern, “Security arguments for digital signatures
and blind signatures,” J. Cryptol., vol. 13, no. 3, pp. 361–396, Jun.
2000.
[37] T. Li, H. Wang, D. He, and J. Yu, “Designated-verifier aggregate
signature scheme with sensitive data privacy protection for permissioned
blockchain-assisted IIoT,” IEEE Trans. Inf. Forensics Security, vol. 18,
pp. 4640–4651, 2023.
[38] Z. Gong, T. Gao, and N. Guo, “PCAS: Cryptanalysis and improvement
of pairing-free certificateless aggregate signature scheme with conditional privacy-preserving for VANETs,” Ad Hoc Netw., vol. 144, May
2023, Art. no. 103134.
[39] Z. Wang and Q. Wu, “A practical lattice-based sequential aggregate
signature,” in Proc. 13th Int. Conf. Provable Secur., 2019, pp. 94–109.

Qichang Li (Graduate Student Member, IEEE) is
currently pursuing the Ph.D. degree with Hangzhou
Dianzi University, China. His research interests
include the Internet of Vehicles and identity authentication.

Yingjie Xia (Senior Member, IEEE) received the
Ph.D. degree from the College of Computer Science,
Zhejiang University, Hangzhou, China, in 2009.
He was affiliated as a Research Scientist with the
National Center for Supercomputing Applications
(NCSA), University of Illinois Urbana–Champaign
(UIUC), Champaign, IL, USA. He is currently
a Distinguished Professor with Hangzhou Dianzi
University, a Distinguished Research Fellow with
Zhejiang University, and the CEO of Hangzhou
Yuantiao Technology Company. His research interests include intelligent transportation and information security.

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

2200

IEEE JOURNAL ON SELECTED AREAS IN COMMUNICATIONS, VOL. 44, 2026

Xuejiao Liu received the Ph.D. degree from
Huazhong Normal University, Wuhan, China, in
2011. She is currently a Professor with the School
of Information Science and Technology, Hangzhou
Normal University, Hangzhou, China. Her research
interests include network security and vehicular networks.

Xiyuan Chen received the Ph.D. degree from the
College of Computer Science, Zhejiang University,
Hangzhou, China. She is currently a Lecturer with
the College of Computer Science, Hangzhou Dianzi
University, Hangzhou. Her research interests include
information security and intelligent transportation.

Zhiquan Liu received the B.S. degree from the
School of Science, Xidian University, Xi’an, China,
in 2012, and the Ph.D. degree from the School of
Computer Science and Technology, Xidian University, in 2017.
He is currently a Full Professor with the College
of Cyber Security, Jinan University, Guangzhou,
China. His current research focuses on security,
trust, privacy, and intelligence in vehicular networks. He serves as an Area Editor/Associate
Editor for multiple SCI-index journals, such as
IEEE T RANSACTIONS ON I NFORMATION F ORENSICS AND S ECURITY,
IEEE T RANSACTIONS ON I NDUSTRIAL I NFORMATICS, IEEE I NTERNET OF
T HINGS J OURNAL, Information Fusion, IEEE Network, Computer Networks,
and Journal of Systems Architecture.

Zhen Guo (Member, IEEE) received the B.S. degree
from the School of Information and Communication
Engineering, Hainan University, Haikou, China, in
2010, and the Ph.D. degree from the School of
Cryptography and Information Security, Xidian University, Xi’an, China, in 2018.
She is currently an Associate Professor and the
Deputy Dean of the School of Cyberspace Security
(School of Cryptography), Hainan University. Her
current research focuses on data security, privacy
protection, and the IoT security. She serves as the
Youth Editorial Board Member for Journal of Communications and Journal
of Network and Information Security.

Zhe Liu (Senior Member, IEEE) received the B.S.
and M.S. degrees from Shandong University, China,
in 2008 and 2011, respectively, and the Ph.D. degree
from the University of Luxembourg, Luxembourg,
in 2015. He is currently a Professor with Zhejiang
Laboratory, Hangzhou, China. He has co-authored
more than 80 research peer-reviewed journals and
conference papers. His research interests include
security, privacy, and cryptography solutions for
the Internet of Things. He serves as a Program
Committee Member for more than 60 international
conferences, including program chairs in INSCRYPT 2019, CRYPTOIC 2019,
and ACM China SIGSAC 2020. He was a recipient of the prestigious FNR
Awards-Outstanding Ph.D. Thesis Award in 2016, the ACM China SIGSAC
Rising Star Award in 2017, as well as the DAMO Academy Young Fellow in
2019.

Liming Fang (Member, IEEE) received the Ph.D.
degree in computer science from Nanjing University
of Aeronautics and Astronautics, Nanjing, China,
in 2012. He was a Post-Doctoral Researcher in
information security with the City University of
Hong Kong. He is currently a Professor with the
College of Computer Science and Technology, Nanjing University of Aeronautics and Astronautics.
He was the Principal Investigator and the Main
Participant in more than 20 key projects, including
the National Natural Science Foundation of China
and the 863/973 Plan. He has authored or co-authored more than 80 papers
in journals and international conferences, including Theoretical Computer
Science, Designs, Codes and Cryptography, IEEE T RANSACTIONS ON
D EPENDABLE AND S ECURE C OMPUTING, and IEEE T RANSACTIONS ON
I NFORMATION F ORENSICS AND S ECURITY. His current research interests
include information security, applied cryptography, AI security, blockchain,
and proxy re-encryption.

Authorized licensed use limited to: Thammasat University. Downloaded on October 15,2026 at 14:53:30 UTC from IEEE Xplore. Restrictions apply.

