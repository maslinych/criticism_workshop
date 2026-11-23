Review the analyst's statements on the following part of an article. Answer with the JSON object only.

Periodical: {{periodical}}
Date of issue: {{issue_date}}
Article identifier: {{article_id}}
Heading (as detected when the corpus was built; may be missing or wrong): {{heading}}

The article is long, so it is reviewed in {{part_count}} parts. This is part {{part_number}} of {{part_count}}.

The context, between the markers <<<CONTEXT and CONTEXT>>>, is text from earlier in the article: its beginning and the text just before this part ("[…]" marks text left out). Use it only to understand the part.

<<<CONTEXT
{{context}}
CONTEXT>>>

The part is between the markers <<<PART and PART>>>.

<<<PART
{{text}}
PART>>>

The analyst's statements on this part are between the markers <<<STATEMENTS and STATEMENTS>>>.

<<<STATEMENTS
{{statements_json}}
STATEMENTS>>>
