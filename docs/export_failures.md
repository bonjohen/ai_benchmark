OpenAI			
2026-03-31T12:00:04.550093Z	[warning  ]	access_forbidden	url=https://openai.com/news/product-releases/
2026-03-31T12:00:04.553137Z	[warning  ]	access_forbidden	url=https://openai.com/api/pricing/
2026-03-31T12:00:04.554739Z	[warning  ]	fetch_error	attempt=0 error='403 Forbidden' organization=OpenAI task_id=ac551656ab4a4ba2b2c0770e4aeb0416 url=https://openai.com/news/product-releases/
2026-03-31T12:00:04.556945Z	[warning  ]	access_forbidden	url=https://openai.com/index/system-cards/
2026-03-31T12:00:04.570966Z	[warning  ]	fetch_error	attempt=0 error='403 Forbidden' organization=OpenAI task_id=781840f435d44caa92f636a28d4edee2 url=https://openai.com/api/pricing/
2026-03-31T12:00:04.585648Z	[warning  ]	fetch_error	attempt=0 error='403 Forbidden' organization=OpenAI task_id=f569fd331dde401086aad47ed18846fb url=https://openai.com/index/system-cards/
2026-03-31T12:00:04.597372Z	[warning  ]	access_forbidden	url=https://platform.openai.com/docs/changelog
2026-03-31T12:00:04.600063Z	[warning  ]	fetch_error	attempt=0 error='403 Forbidden' organization=OpenAI task_id=29eacd7c2cfb49eb8db64fb10ed996de url=https://platform.openai.com/docs/changelog
2026-03-31T12:00:04.605927Z	[warning  ]	access_forbidden	url=https://platform.openai.com/docs/models
2026-03-31T12:00:04.613807Z	[warning  ]	fetch_error	attempt=0 error='403 Forbidden' organization=OpenAI task_id=02f4c3bfe32c41fc836e60f0a99470f1 url=https://platform.openai.com/docs/models
            
xAI			
2026-03-31T12:00:07.963206Z	[warning  ]	access_forbidden	url=https://x.ai/news
2026-03-31T12:00:07.964981Z	[warning  ]	fetch_error	attempt=0 error='403 Forbidden' organization=xAI task_id=166a813573cf4f87a0d77b4a4865dd3b url=https://x.ai/news
            
Cohere			
2026-03-31T12:00:09.775139Z	[debug    ]	cohere_html_extraction_empty	note='Expected: Cohere pages are JS-rendered shells. RSS is primary.' page_type=pricing
2026-03-31T12:00:10.303700Z	[debug    ]	cohere_html_extraction_empty	note='Expected: Cohere pages are JS-rendered shells. RSS is primary.' page_type=blog
            
Hugging Face			
2026-03-31T12:23:36.873223Z	[debug    ]	low_value_stale_dates	page=https://huggingface.co/gaia-benchmark
2026-03-31T12:23:36.873328Z	[debug    ]	low_value_page_filtered	count=11 organization='GAIA benchmark' task_id=0566d8a0f5324e80bfbe38705268da3a url=https://huggingface.co/gaia-benchmark
            
Semantic			
2026-03-31T12:23:36.670852Z	[warning  ]	semantic_scholar_no_api_key	hint='Set AI_BENCH_SEMANTIC_SCHOLAR_API_KEY for higher rate limits'
2026-03-31T12:24:40.151151Z	[warning  ]	api_rate_limited	attempt=1 retry_after=30 url=https://api.semanticscholar.org/graph/v1/paper/search
2026-03-31T12:25:10.280302Z	[warning  ]	api_rate_limited	attempt=2 retry_after=30 url=https://api.semanticscholar.org/graph/v1/paper/search
2026-03-31T12:25:40.413688Z	[warning  ]	api_rate_limited	attempt=3 retry_after=30 url=https://api.semanticscholar.org/graph/v1/paper/search
