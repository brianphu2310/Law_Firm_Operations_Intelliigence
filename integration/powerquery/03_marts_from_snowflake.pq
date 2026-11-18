// Power Query reading the marts straight from Snowflake (Excel prompts for your Snowflake login on first refresh).
// Replace YOUR_ACCOUNT with the account identifier, e.g. om54953.ap-southeast-2 (Snowsight > account menu > Account identifier).
let
    Source = Snowflake.Databases("YOUR_ACCOUNT.snowflakecomputing.com", "COMPUTE_WH"),
    Marts  = Source{[Name = "LAW_FIRM"]}[Data]{[Name = "MARTS", Kind = "Schema"]}[Data],
    Aged   = Marts{[Name = "AGED_RECEIVABLES", Kind = "View"]}[Data],
    Typed  = Table.TransformColumnTypes(Aged, {{"BALANCE_DUE", Currency.Type}, {"DAYS_PAST_DUE", Int64.Type}})
in
    Typed
