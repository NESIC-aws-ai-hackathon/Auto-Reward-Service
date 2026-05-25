import boto3

ddb = boto3.resource('dynamodb', region_name='ap-northeast-1')
t = ddb.Table('ArsTable')

# Count EXPENSE records
r = t.scan(
    FilterExpression='begins_with(SK, :sk)',
    ExpressionAttributeValues={':sk': 'EXPENSE#'},
    Select='COUNT'
)
print(f"EXPENSE count: {r['Count']}")

# Count LIFELOG records
r2 = t.scan(
    FilterExpression='begins_with(SK, :sk)',
    ExpressionAttributeValues={':sk': 'LIFELOG#'},
    Select='COUNT'
)
print(f"LIFELOG count: {r2['Count']}")

# Count CHAT records
r3 = t.scan(
    FilterExpression='begins_with(SK, :sk)',
    ExpressionAttributeValues={':sk': 'CHAT#'},
    Select='COUNT'
)
print(f"CHAT count: {r3['Count']}")

# List all PKs
r4 = t.scan(
    FilterExpression='begins_with(SK, :sk)',
    ExpressionAttributeValues={':sk': 'IDENTITY#'},
)
for item in r4['Items']:
    print(f"  {item['PK']} / {item['SK']} -> user_id={item.get('user_id','?')}")

# Show last 5 EXPENSE if any
r5 = t.scan(
    FilterExpression='begins_with(SK, :sk)',
    ExpressionAttributeValues={':sk': 'EXPENSE#'},
    Limit=5
)
print("\n--- Recent EXPENSE records ---")
for item in r5['Items']:
    print(f"  {item['PK']} | {item['SK']} | {item.get('item','?')} | {item.get('amount','?')}")

# Show LIFELOG entries
r6 = t.scan(
    FilterExpression='begins_with(SK, :sk)',
    ExpressionAttributeValues={':sk': 'LIFELOG#'},
)
print(f"\n--- All LIFELOG records ({r6['Count']}) ---")
for item in r6['Items']:
    print(f"  {item['PK']} | {item['SK']} | emotion={item.get('emotion','?')} | ctx={item.get('context','?')[:50]}")

# Show MONTHLY_SUMMARY
r7 = t.scan(
    FilterExpression='begins_with(SK, :sk)',
    ExpressionAttributeValues={':sk': 'MONTHLY_SUMMARY#'},
)
print(f"\n--- MONTHLY_SUMMARY ({r7['Count']}) ---")
for item in r7['Items']:
    print(f"  {item['PK']} | {item['SK']} | total={item.get('total_spent','?')} | count={item.get('expense_count','?')}")

# Show CONVERSATION_STATE
r8 = t.scan(
    FilterExpression='begins_with(SK, :sk)',
    ExpressionAttributeValues={':sk': 'CONVERSATION_STATE#'},
)
print(f"\n--- CONVERSATION_STATE ---")
for item in r8['Items']:
    print(f"  {item['PK']} | flow={item.get('current_flow','?')} | step={item.get('step','?')}")
