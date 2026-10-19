# AWS price evidence — 2026-10-19

Official public AWS Price List responses retrieved sequentially into ignored `data/tmp/aws-pricing`; no authenticated resource creation. Mumbai files except global CloudFront with **India** entries selected. USD OnDemand, first applicable tier, no free allowances assumed. Rates support `DEPLOYMENT_PLAN.md`, not an account bill or guaranteed maximum. Cached JSON total under4MiB; refresh before a delayed approval. `current` URLs are mutable; hashes identify the actually inspected responses.

| Service / official response | Publication UTC | Response SHA256 |
|---|---|---|
| [AmazonECS / ap-south-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/ap-south-1/index.json) | 2026-09-11T12:44:25Z | `8533485ab150774c72cae97e24e0794b5d64d74c65ef609ea2a17b91fc495e13` |
| [AWSELB / ap-south-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/ap-south-1/index.json) | 2026-09-11T12:45:44Z | `1aeb7a7655b5c72d762976ceed43fda9cf7378abe06d0a26da3312059266ccf8` |
| [AmazonVPC / ap-south-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/ap-south-1/index.json) | 2026-10-16T22:43:21Z | `c2b9c0707b71a6ccd51c72229cf2f676c5e557a0c74473856281a83a9d75d0a4` |
| [AmazonECR / ap-south-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECR/current/ap-south-1/index.json) | 2026-09-11T12:44:25Z | `78fc4d7a1086de738294d01890d9955c184e570dfc0665f5921f5fb150ddd550` |
| [AmazonS3 / ap-south-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/ap-south-1/index.json) | 2026-10-15T17:35:40Z | `fd89d71c6ecaf0c4f48659abd24fa9f44b6957b76467bcfdddec92e1dec00828` |
| [AmazonCloudWatch / ap-south-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/ap-south-1/index.json) | 2026-10-07T11:55:40Z | `0605cd5cd1f4fc59124546937e4985c82a8d0cff463a4381e9731ee49dcb9e5e` |
| [AWSDataTransfer / ap-south-1](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/ap-south-1/index.json) | 2026-09-16T13:22:08Z | `90fa51b6592565f895328c28ca6c22a925619f8772a02ff46a61e6c9e1be8001` |
| [AmazonCloudFront / global](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudFront/current/index.json) | 2026-10-19T15:05:00Z | `17e3e9aeb5add88d1f6ba78f7fdcfb2405a83a9388228adc46c8ae09da9ca2ce` |

Selected product SKUs / units (do not confuse Gateway/Network/Outposts/Reserved LCU with Application ALB):

| SKU | Selected usage | USD rate |
|---|---|---:|
| KV4FGA39G96M59TH | APS3-Fargate-vCPU-Hours:perCPU, Linux x86 | 0.04256/vCPU-h |
| N4Q5MGA6V9TFA2MG | APS3-Fargate-GB-Hours | 0.004655/GB-h |
| WJ2MHASNP2ZNKFXX | Application LoadBalancer-hour | 0.0239/h |
| HFFD75W4GFXQPHZR | Application used LCU | 0.008/LCU-h |
| H6SHSM3KDNNZRM9E | In-use public IPv4 | 0.005/address-h |
| WRGBK4S2T45GRPMB | ECR storage | 0.10/GB-month |
| USGUTP2JY23N9GH2 | S3 General Purpose Standard, first50TB/month | 0.025/GB-month |
| UJ844B8DVMQUFJQP | S3 Tier1 PUT/COPY/POST/LIST | 0.000005/request |
| SF3QQQMZGA3PPF33 | S3 Tier2 GET/other | 0.0000004/request |
| JBQP6QEETS2BK5DQ | Standard CloudWatch logs ingestion | 0.67/GB |
| M9PG5USRE2QBB6FU | CloudWatch logs storage | 0.03/GB-month |
| UKQ34C8EAAJUUK8Q | Mumbai internet outbound first10TB beyond global free tier | 0.1093/GB |
| XVZYVSAH88373VKR | CloudFront India viewer outbound first10TB | 0.109/GB |
| GJTTXSYXV43ANXTQ | CloudFront India HTTPS requests | 0.0000012/request |
| YR9KNSXHQ8YZU3RU | CloudFront India transfer toward origin | 0.16/GB |

No domain/registrar quote obtained. No account-specific credits/free-tier eligibility assumed. The monthly scenario's1GB internet egress could be within an account-wide free allowance, but that allowance may be consumed by unrelated projects. India visitor-location assumption is separate from Mumbai origin. CloudFront plan assumes pay-as-you-go, not a flat-rate bundle; verify account/distribution pricing before deploying. AWS origin→CloudFront data transfer is not double billed. Taxes, forex, excess traffic/storage, additional ALB addresses, IAM/quota issues and forgotten resources are outside the subtotal; see explicit approval and cleanup gates in the deployment plan.
