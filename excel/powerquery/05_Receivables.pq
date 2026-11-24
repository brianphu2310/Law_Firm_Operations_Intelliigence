// Query name: Receivables  ->  load to the "Receivables" sheet as table tblAgeing
// Receivables ageing by client (sql/analysis/07_receivables_ageing_by_client.sql).
let
    Source = fnQueryResult("docs/query_results", "07_receivables_ageing_by_client"),
    Money  = {"ar_incl_gst", "not_yet_due", "days_1_30", "days_31_60", "days_61_90", "days_90_plus"},
    Typed  = Table.TransformColumnTypes(Source,
                 List.Transform(Money, each {_, Currency.Type}) &
                 {{"client_name", type text}, {"open_invoices", Int64.Type}, {"max_days_past_due", Int64.Type}, {"pct_overdue", type number},
                  {"pct_of_firm_ar", type number}, {"overdue_rank", Int64.Type}, {"collections_action", type text}}, "en-AU")
in
    Typed
