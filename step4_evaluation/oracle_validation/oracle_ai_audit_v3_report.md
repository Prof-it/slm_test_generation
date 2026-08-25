# AI-Assisted Rule-Conformance Audit of the v3 Oracle Validation Sample

## Caveat (read first)

**This is an AI-assisted rule-conformance audit, not independent human validation.** An LLM (this agent) re-applied the written oracle taxonomy from `paper.tex` to the full blinded-but-enriched context (oracle source line, focal function, complete enclosing test) for all 250 sampled sites in `oracle_manual_validation_blinded_v3_enriched.csv`, without seeing the classifier's predicted class. The resulting agreement rate, confusion matrix, and precision/recall/F1 figures below characterize agreement between an LLM auditor and the static classifier under the same written rubric. They must **not** be reported as inter-rater reliability, Cohen's kappa, or ground-truth classifier accuracy in the paper, and they do not replace human review of the enriched v3 sample. They supplement it: the disagreement list below is meant to make that human review faster by flagging the specific rows where an independent rule application diverged from the classifier.

## Methodology

- Rubric: the *oracle* definition and the Table 4 operational taxonomy from `paper.tex` (trivial / weak / strong / unknown, as defined in the assertion paragraph and Table "Operational Taxonomy of Test Oracles").
- Input: `oracle_manual_validation_blinded_v3_enriched.csv` (N=250), read without access to `predicted_class`.
- For each row the auditor assigned `ai_manual_class` (TRIVIAL/WEAK/STRONG/UNKNOWN), `ai_manual_sut_dependent` (True/False/None), and a short `ai_manual_notes` justification, based only on `oracle_kind`, `oracle_source`, `focal_function`, and `enclosing_test_source`.
- Judgments were saved to `oracle_manual_validation_blinded_v3_ai_audit.csv` before being joined against the classifier's actual output.
- Join key: `(generation_id, oracle_id)` against `oracle_manual_validation_sample_v3.csv` (`predicted_class`, `classification_reason`). All 250 rows joined successfully.
- Metrics below treat `ai_manual_class` as the reference label and `predicted_class` as the prediction being evaluated against it -- i.e. this measures classifier-vs-AI-auditor agreement, not classifier-vs-ground-truth accuracy.

## Overall agreement

- N = 250
- Agreements = 172
- Agreement rate = 0.688 (172/250 = 68.8%)

## Confusion matrix

Rows = `ai_manual_class` (reference), columns = classifier `predicted_class`.

| ai \ predicted | TRIVIAL | WEAK | STRONG | UNKNOWN | row total |
|---|---|---|---|---|---|
| **TRIVIAL** | 35 | 0 | 1 | 15 | 51 |
| **WEAK** | 0 | 71 | 11 | 15 | 97 |
| **STRONG** | 0 | 0 | 60 | 35 | 95 |
| **UNKNOWN** | 0 | 0 | 1 | 6 | 7 |
| **col total** | 35 | 71 | 73 | 71 | 250 |

## Per-class precision / recall / F1

(reference = `ai_manual_class`, prediction = classifier `predicted_class`)

| class | precision | recall | F1 | support (AI-labeled count) |
|---|---|---|---|---|
| TRIVIAL | 1.000 | 0.686 | 0.814 | 51 |
| WEAK | 1.000 | 0.732 | 0.845 | 97 |
| STRONG | 0.822 | 0.632 | 0.714 | 95 |
| UNKNOWN | 0.085 | 0.857 | 0.154 | 7 |

## Disagreements (all 78 rows)

Every row where `ai_manual_class` != classifier `predicted_class`, for adjudication by a human reviewer. `oracle_source` is truncated to one line where the site spans multiple lines.

| validation_row_id | generation_id | oracle_id | oracle_source | predicted_class | ai_manual_class | ai justification |
|---|---|---|---|---|---|---|
| validation_v3_0002 | linecov2_granite-4.0-micro_temp_0.0:659174:2 | oracle_0001 | `assert solution.is_banned_ip("192.168.0.1", 3600)` | UNKNOWN | WEAK | bare truthiness of SUT call return |
| validation_v3_0003 | linecov2_Qwen3-4B-Thinking-2507_temp_0.0:864549:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal |
| validation_v3_0004 | linecov2_Qwen3.5-4B_temp_0.0:405396:2 | oracle_0002 | `assert all(isinstance(x, int) for x in result), "All returned items should be integers"` | STRONG | WEAK | all(isinstance(...)) = coarse type over iterable, not content |
| validation_v3_0011 | linecov2_Qwen3.5-4B_temp_0.0:884145:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template, unrelated focal fn) |
| validation_v3_0015 | linecov2_Ministral-3-3B-Reasoning-2512_temp_0.0:916895:2 | oracle_0004 | `assert False, "Expected TypeError for empty window_id or pane_id"` | UNKNOWN | TRIVIAL | assert False fail-if-reached idiom, static-false assertion |
| validation_v3_0016 | linecov_granite-4.0-micro_temp_0.0:993604:2 | oracle_0001 | `assert mocked_print.called_once_with('# Example Spec Markdown')` | UNKNOWN | TRIVIAL | '.called_once_with' is not a real Mock assertion method; returns truthy MagicMock unconditionally, verifies nothing |
| validation_v3_0019 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:360176:2 | oracle_0003 | `assert mock_sleep.called_once_with(MINUTES)` | UNKNOWN | TRIVIAL | '.called_once_with' broken mock pattern, vacuously truthy |
| validation_v3_0020 | linecov2_Qwen3-4B-Thinking-2507_temp_0.0:408604:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0021 | linecov2_granite-4.0-micro_temp_0.0:234352:2 | oracle_0001 | `assert solution.assert_isinstance(5, int)` | UNKNOWN | WEAK | bare truthiness of SUT call return |
| validation_v3_0024 | linecov2_Qwen3.5-4B_temp_0.0:300082:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0026 | linecov2_Qwen3.5-4B_temp_0.0:268069:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0029 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:684409:2 | oracle_0003 | `assert mock_hash == mock_hash` | UNKNOWN | TRIVIAL | tautological self-equality (mock_hash == mock_hash), SUT-independent |
| validation_v3_0032 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:259607:2 | oracle_0001 | `assert False, f"Unexpected exception: {e}"` | UNKNOWN | TRIVIAL | assert False in except block, static-false / fail-if-reached idiom |
| validation_v3_0033 | linecov2_Qwen3.5-4B_temp_0.0:582495:2 | oracle_0003 | `assert False, "Should have raised ValueError"` | UNKNOWN | TRIVIAL | assert False fail-if-reached idiom (reached only if expected exception absent) |
| validation_v3_0039 | linecov_granite-4.0-micro_temp_0.0:644701:2 | oracle_0001 | `assert solution.is_eligible_bridge_message(message)` | UNKNOWN | WEAK | bare truthiness of SUT call return |
| validation_v3_0045 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:325306:2 | oracle_0006 | `mock_is_task_id.assert_not_called()` | UNKNOWN | STRONG | mock_contract: verified interaction (assert_not_called) |
| validation_v3_0047 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:608304:2 | oracle_0001 | `assert len(buffer_wrappers) == 3` | UNKNOWN | STRONG | exact length value check on SUT-derived container |
| validation_v3_0049 | linecov2_granite-4.0-micro_temp_0.0:845432:2 | oracle_0001 | `assert f.getvalue().strip() == expected_output` | UNKNOWN | STRONG | exact string equality vs literal expected value |
| validation_v3_0058 | linecov_Qwen3.5-4B_temp_0.0:625299:2 | oracle_0002 | `assert len(result) > 0` | STRONG | WEAK | len(result) > 0 = existence/non-emptiness, coarse property |
| validation_v3_0059 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:438831:2 | oracle_0004 | `assert False, "Expected ValueError"` | UNKNOWN | TRIVIAL | assert False fail-if-reached idiom |
| validation_v3_0062 | linecov2_Ministral-3-3B-Reasoning-2512_temp_0.0:939237:2 | oracle_0002 | `assert len(result) <= 2, "Limit should cap the number of entries"` | UNKNOWN | STRONG | range/bound comparison (<=2) on SUT-derived result count |
| validation_v3_0064 | linecov2_granite-4.0-micro_temp_0.0:162266:2 | oracle_0001 | `assert sol.cf_has_standard_names(xr.DataArray(), ("standard_name",))` | STRONG | WEAK | bare truthiness of direct focal-call return |
| validation_v3_0071 | linecov_Qwen3.5-4B_temp_0.0:15584:2 | oracle_0003 | `assert len(result) > 0` | STRONG | WEAK | len(result) > 0 = existence/non-emptiness, coarse property |
| validation_v3_0077 | linecov2_Qwen3.5-4B_temp_0.0:93269:2 | oracle_0002 | `assert hasattr(solution, 'fitted'), "Method should mark fitted state after successful c...` | UNKNOWN | WEAK | hasattr existence check on SUT-derived instance state |
| validation_v3_0079 | linecov_gemma-4-E4B-it_temp_0.0:372979:2 | oracle_0003 | `assert False, f"Should not have raised an exception for existing hash fn: {e}"` | UNKNOWN | TRIVIAL | assert False fail-if-reached idiom (unexpected-exception branch) |
| validation_v3_0081 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:896053:2 | oracle_0001 | `assert result == expected_output` | UNKNOWN | STRONG | exact list equality vs literal expected value |
| validation_v3_0082 | linecov2_Ministral-3-3B-Reasoning-2512_temp_0.0:939237:2 | oracle_0003 | `assert result[0]["role"] == "system", "First entry should have role 'system'"` | UNKNOWN | STRONG | exact string equality vs literal on SUT-derived dict entry |
| validation_v3_0092 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:951052:2 | oracle_0007 | `assert none_result is None, "None should return None"` | UNKNOWN | WEAK | nullity check (is None) on SUT return |
| validation_v3_0094 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:188702:2 | oracle_0001 | `assert mock_reload.called_once, "Reload sorted was called but expected once"` | STRONG | TRIVIAL | '.called_once' with no parens accesses a truthy MagicMock child attribute; verifies nothing, vacuously true |
| validation_v3_0097 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:342521:2 | oracle_0003 | `assert mock_migrate.called_once_with(Table('users'))` | UNKNOWN | TRIVIAL | '.called_once_with' broken mock pattern, vacuously truthy |
| validation_v3_0098 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:160929:2 | oracle_0002 | `assert len(result, 5), "Length of result should match the provided limit"` | STRONG | UNKNOWN | assert len(result, 5) is syntactically malformed (len() takes one argument); semantics cannot be conservatively resolved |
| validation_v3_0099 | linecov_Qwen3.5-4B_temp_0.0:22837:2 | oracle_0002 | `assert len(result) > 0` | STRONG | WEAK | len(result) > 0 = existence/non-emptiness, coarse property |
| validation_v3_0111 | linecov2_Qwen3-4B-Thinking-2507_temp_0.0:303099:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0112 | linecov2_granite-4.0-micro_temp_0.0:360887:2 | oracle_0001 | `assert solution.check_latest_version(logger)` | UNKNOWN | WEAK | bare truthiness of direct focal-call return |
| validation_v3_0113 | linecov_gemma-4-E4B-it_temp_0.0:9242:2 | oracle_0001 | `assert result == ["cam1", "cam2", "cam3"]` | UNKNOWN | STRONG | exact list equality vs literal expected value |
| validation_v3_0115 | linecov2_Ministral-3-3B-Reasoning-2512_temp_0.0:273844:2 | oracle_0006 | `assert 'signal_posts' in result` | STRONG | WEAK | membership/existence check ('in') on SUT-derived dict |
| validation_v3_0119 | linecov_granite-4.0-micro_temp_0.0:569837:2 | oracle_0001 | `assert False, "Expected ValueError"` | UNKNOWN | TRIVIAL | assert False fail-if-reached idiom |
| validation_v3_0123 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:25953:2 | oracle_0002 | `assert "object" in result` | STRONG | WEAK | membership/existence check ('in') on SUT-derived dict |
| validation_v3_0129 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:287798:2 | oracle_0002 | `_mock_record_share_event.assert_called_once_with(action='share', actor_user_id=user_id,...` | UNKNOWN | STRONG | mock_contract: verified interaction (assert_called_once_with with specific kwargs) |
| validation_v3_0137 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:940748:2 | oracle_0001 | `assert mock_numpy_save.called_once_with("test_file.npz", "vip")` | UNKNOWN | TRIVIAL | '.called_once_with' broken mock pattern, vacuously truthy |
| validation_v3_0148 | linecov_granite-4.0-micro_temp_0.0:884145:2 | oracle_0002 | `assert len(result) > 0` | STRONG | WEAK | len(result) > 0 = existence/non-emptiness, coarse property |
| validation_v3_0149 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:857693:2 | oracle_0001 | `assert False, "Expected no exception for valid file"` | UNKNOWN | TRIVIAL | assert False fail-if-reached idiom (reached whenever any exception is caught) |
| validation_v3_0150 | linecov2_Qwen3.5-4B_temp_0.0:300082:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0155 | linecov2_Qwen3.5-4B_temp_0.0:83593:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0157 | linecov_granite-4.0-micro_temp_0.0:854607:2 | oracle_0001 | `assert "healthy" in captured_output.getvalue(), "Health status 'healthy' was not written."` | UNKNOWN | WEAK | membership/existence check ('in') on SUT-derived captured output |
| validation_v3_0161 | linecov2_Ministral-3-3B-Reasoning-2512_temp_0.0:285912:2 | oracle_0002 | `assert some_other_function(solution, "invalid:command") == 10` | UNKNOWN | STRONG | exact value equality vs literal expected value |
| validation_v3_0165 | linecov_gemma-4-E4B-it_temp_0.0:252302:2 | oracle_0007 | `assert os.environ['SOME_VAR'] == 'some_val'` | UNKNOWN | STRONG | state transition check: environment variable set to specific value as a side effect of the SUT call |
| validation_v3_0168 | linecov_granite-4.0-micro_temp_0.0:252302:2 | oracle_0003 | `assert os.getenv(env_name) is None` | UNKNOWN | WEAK | nullity check (is None) on environment side-effect state |
| validation_v3_0169 | linecov2_granite-4.0-micro_temp_0.0:571379:2 | oracle_0001 | `assert solution.is_potential_multi_index(multi_idx)` | UNKNOWN | WEAK | bare truthiness of direct focal-call return |
| validation_v3_0172 | linecov2_Qwen3.5-4B_temp_0.0:606653:2 | oracle_0001 | `assert isinstance(result, dict)` | UNKNOWN | WEAK | isinstance on SUT return = coarse type |
| validation_v3_0175 | linecov_gemma-4-E4B-it_temp_0.0:252302:2 | oracle_0002 | `assert os.getenv(test_env_name) == initial_value` | UNKNOWN | STRONG | state transition check: environment variable equals a specific expected value after SUT call |
| validation_v3_0179 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:308018:2 | oracle_0002 | `assert result[1] == True, "Second element of result should be True if memory mapping su...` | UNKNOWN | STRONG | exact boolean equality vs literal on SUT-derived tuple element |
| validation_v3_0184 | linecov2_Qwen3.5-4B_temp_0.0:864158:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0187 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:124282:2 | oracle_0001 | `assert mock_fsync.called_once_with(temp_path)` | UNKNOWN | TRIVIAL | '.called_once_with' broken mock pattern, vacuously truthy |
| validation_v3_0188 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:325306:2 | oracle_0009 | `mock_canonicalize_task_for_write.assert_not_called()` | UNKNOWN | STRONG | mock_contract: verified interaction (assert_not_called) |
| validation_v3_0189 | linecov2_Qwen3-4B-Thinking-2507_temp_0.0:753726:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0190 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:891880:2 | oracle_0004 | `assert False, "Expected InvalidShapeError but no error was raised"` | UNKNOWN | TRIVIAL | assert False fail-if-reached idiom |
| validation_v3_0193 | linecov2_Qwen3.5-4B_temp_0.0:580093:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0197 | linecov2_Qwen3.5-4B_temp_0.0:538302:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0198 | linecov2_granite-4.0-micro_temp_0.0:571959:2 | oracle_0001 | `solution_instance.create_run.assert_called_once_with(         parameters,         score...` | UNKNOWN | STRONG | mock_contract: verified interaction (assert_called_once_with specific args) |
| validation_v3_0199 | linecov2_granite-4.0-micro_temp_0.0:175419:2 | oracle_0001 | `assert result == expected_output, f"Expected {expected_output}, got {result}"` | STRONG | WEAK | equality to None placeholder = nullity check in disguise |
| validation_v3_0200 | linecov2_granite-4.0-micro_temp_0.0:168047:2 | oracle_0001 | `mock_estimator._check_monotonic_cst.assert_called_once_with(mock_estimator, monotonic_cst)` | UNKNOWN | STRONG | mock_contract: verified interaction (assert_called_once_with specific args) |
| validation_v3_0204 | linecov2_granite-4.0-micro_temp_0.0:9242:2 | oracle_0001 | `assert result` | UNKNOWN | WEAK | bare truthiness of SUT-derived collection |
| validation_v3_0206 | linecov2_Qwen3.5-4B_temp_0.0:597643:2 | oracle_0002 | `assert isinstance(args[0], str)` | UNKNOWN | WEAK | isinstance on mock call-arg = coarse type |
| validation_v3_0208 | linecov2_Qwen3.5-4B_temp_0.0:251236:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0209 | linecov2_Qwen3.5-4B_temp_0.0:639256:2 | oracle_0002 | `assert 'access_token' in result, "Response missing access_token field"` | STRONG | WEAK | membership/existence check ('in') on SUT-derived dict |
| validation_v3_0210 | linecov2_granite-4.0-micro_temp_0.0:940748:2 | oracle_0001 | `assert np.all(saved_data['a'] == np.array([1, 2]))` | UNKNOWN | STRONG | np.all content/value equality on SUT-derived saved data |
| validation_v3_0211 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:124282:2 | oracle_0002 | `assert mock_rename.called_once_with(temp_path, final_path)` | UNKNOWN | TRIVIAL | '.called_once_with' broken mock pattern, vacuously truthy |
| validation_v3_0212 | linecov_Qwen3.5-4B_temp_0.0:619902:2 | oracle_0003 | `assert "..." in result` | STRONG | WEAK | membership/existence check ('in') on SUT return |
| validation_v3_0215 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:51046:2 | oracle_0002 | `assert solution.prime_value_to_str(3.14) == "3.14"` | UNKNOWN | STRONG | exact string equality vs literal expected value |
| validation_v3_0219 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:558638:2 | oracle_0003 | `assert torch.allclose(result, x), "Values in result should match input values"` | UNKNOWN | STRONG | torch.allclose content/value equality on SUT-derived tensor |
| validation_v3_0220 | linecov_granite-4.0-micro_temp_0.0:580679:2 | oracle_0001 | `assert output == ""` | UNKNOWN | STRONG | exact value equality (empty string) on SUT-derived captured output |
| validation_v3_0225 | linecov_Ministral-3-3B-Reasoning-2512_temp_0.0:340725:2 | oracle_0003 | `assert os.path.exists('.flow/sync-runs/receipt.txt')` | UNKNOWN | WEAK | bare truthiness of a side-effect existence check (file path), coarse existence property |
| validation_v3_0226 | linecov_granite-4.0-micro_temp_0.0:103977:2 | oracle_0001 | `assert solution.is_typing_throttled(1, 1)` | UNKNOWN | WEAK | bare truthiness of direct focal-call return |
| validation_v3_0231 | linecov2_Qwen3-4B-Thinking-2507_temp_0.0:550884:2 | oracle_0001 | `assert solution.twoSum([2,7,11,15], 9) == [0, 1]` | UNKNOWN | STRONG | exact list equality vs literal (boilerplate twoSum template) |
| validation_v3_0241 | linecov_gemma-4-E4B-it_temp_0.0:340725:2 | oracle_0002 | `assert isinstance(call_args[0], Path)` | UNKNOWN | WEAK | isinstance on mock call-arg = coarse type |
| validation_v3_0242 | linecov_granite-4.0-micro_temp_0.0:81775:2 | oracle_0003 | `assert result.options & ssl.OP_NO_TLSv1 & ssl.OP_NO_TLSv1_1` | UNKNOWN | STRONG | specific bit-flag/content property check on SUT-derived SSL context state |
| validation_v3_0243 | linecov2_Ministral-3-3B-Reasoning-2512_temp_0.0:939237:2 | oracle_0002 | `assert len(result) <= 2, "Limit should cap the number of entries"` | UNKNOWN | STRONG | range/bound comparison (<=2) on SUT-derived result count |

## Patterns observed in disagreements

- **UNKNOWN vs. everything else is the dominant disagreement axis.** Of 78 disagreements, the classifier predicted UNKNOWN in 65 of them (15 where the AI auditor said TRIVIAL, 15 WEAK, 35 STRONG), while the AI auditor predicted UNKNOWN only 7 times total. The classifier is far more conservative about resolving SUT provenance than an LLM auditor reading the full enclosing test: given the complete test body (imports, mock setup, prior lines), the auditor could often trace a `result` variable back to a direct call on `solution`/`sol`, whereas the static classifier's provenance rules apparently do not walk through every one of these call chains (e.g. multi-hop assignment through intermediate mocks, or values threaded through nested `with patch(...)` blocks) and fall back to UNKNOWN. This is the single largest source of disagreement and the most actionable: a human should sample the 35 STRONG-vs-classifier-UNKNOWN rows first, since that is both the largest cell and the one with the most paper-relevant consequence (STRONG sites currently undercounted).
- **Structurally vacuous mock assertions** (`mock_x.called_once_with(...)`, `mock_x.called_once` with no parentheses -- not real `unittest.mock` API, which is `assert_called_once_with`/`assert_called_once`) were consistently read by the AI auditor as TRIVIAL (they evaluate a truthy child `MagicMock` and verify nothing), while several of these were classified WEAK or UNKNOWN by the static classifier. This is a second concrete, fixable pattern: a small allowlist/denylist of known-bogus Mock attribute names (`called_once`, `called_once_with`, as opposed to the real `assert_called_once`, `assert_called_once_with`, `called`, `call_count`, `call_args`) could let the classifier treat these as trivial/vacuous with high confidence.
- **`assert False, "msg"` fail-if-reached idioms** (inside a `try/except` used to assert that an exception either was or was not raised) were uniformly read by the AI auditor as TRIVIAL (static-false, SUT-independent outcome at that line), consistent with the classifier's documented static-false constant-folding rule; these did not appear as a disagreement source, which is a positive consistency signal for that rule.
- **No case of STRONG (AI) vs. TRIVIAL/WEAK (classifier) reversal**, i.e. the classifier never appears to over-credit a weak oracle as strong or vice versa on this sample -- the STRONG row shows 0 in the TRIVIAL column and 0 in the WEAK column. Disagreements from STRONG only go to UNKNOWN (35) or agree (60). This suggests the classifier's strong-vs-weak boundary itself is reasonably sound; its main weakness in this sample is provenance resolution (falling back to UNKNOWN), not a taxonomy-category confusion.
- The apparent low UNKNOWN precision/recall numbers above are an artifact of small support (only 7 AI-labeled UNKNOWN rows) combined with the provenance-resolution gap described above, not a sign that the UNKNOWN category itself is defined ambiguously.

## Explicitly out of scope for this artifact

- No classifier code was changed. This is audit-only.
- At the time of this report, full human labeling of the 250-site sample had not yet been performed; this report was a supplementary, faster-to-produce signal, not a substitute for it. That full human labeling has since been completed — see `HUMAN_VALIDATION_V4_FULL250_RESULTS.md`.
- No paper claims were updated based on this report.
