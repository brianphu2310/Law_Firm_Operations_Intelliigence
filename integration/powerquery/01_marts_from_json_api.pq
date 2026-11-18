// Excel > Data > Get Data > From Other Sources > Blank Query > Advanced Editor, paste, rename the query to the mart name.
// Reads a mart from the Marts JSON API (uvicorn integration.marts_api:app --port 8001) and types the columns.
// MartName: aged_receivables | revenue_monthly | collection_performance
let
    BaseUrl  = "http://127.0.0.1:8001",
    MartName = "aged_receivables",
    Response = Json.Document(Web.Contents(BaseUrl, [RelativePath = "marts/" & MartName, Query = [limit = "50000"]])),
    AsTable  = Table.FromRecords(Response[rows]),
    Typed    = Table.TransformColumnTypes(AsTable, {
                   {"as_at", type date}, {"invoice_date", type date}, {"due_date", type date},
                   {"balance_due", Currency.Type}, {"days_past_due", Int64.Type}})
in
    Typed
