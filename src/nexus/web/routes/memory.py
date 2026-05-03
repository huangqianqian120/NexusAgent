"""记忆管理 API 路由."""

from flask import jsonify, request
import logging

from nexus.memory.store import MemoryStore
from nexus.memory.types import MemoryType, RecordStatus

log = logging.getLogger(__name__)


def _get_memory_store():
    """获取当前工作区的 MemoryStore 实例."""
    from personal_agent.workspace import get_workspace_root

    workspace = get_workspace_root()
    return MemoryStore(workspace)


def _entry_to_dict(entry) -> dict:
    """将 MemoryEntry 转为可 JSON 序列化的字典."""
    from nexus.memory.types import utc_now

    return {
        "id": entry.id,
        "name": entry.name,
        "memory_type": entry.memory_type.value,
        "summary": entry.summary,
        "tags": entry.tags,
        "confidence": entry.confidence,
        "priority": entry.priority,
        "status": entry.status.value,
        "relations": [
            {"target_id": r.target_id, "relation": r.relation, "weight": r.weight}
            for r in entry.relations
        ],
        "source": entry.source,
        "event_time": entry.event_time.isoformat() if entry.event_time else None,
        "ttl_days": entry.ttl_days,
        "metadata": entry.metadata,
        "created_at": entry.created_at.isoformat() if entry.created_at else utc_now().isoformat(),
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else utc_now().isoformat(),
    }


def _content_to_dict(content) -> dict:
    """将 MemoryContent 转为可 JSON 序列化的字典."""
    return {
        "id": content.id,
        "body": content.body,
        "metadata": content.metadata,
    }


def register_routes(app):
    """在 Flask app 上注册记忆管理路由."""

    @app.route("/api/v1/memories", methods=["GET"])
    def list_memories():
        try:
            store = _get_memory_store()
            memory_type = request.args.get("type")
            entries = store.list()
            if memory_type:
                entries = [e for e in entries if e.memory_type.value == memory_type]
            return jsonify({"memories": [_entry_to_dict(e) for e in entries]})
        except Exception as e:
            log.error(f"Error listing memories: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories/<memory_id>", methods=["GET"])
    def get_memory(memory_id):
        try:
            store = _get_memory_store()
            result = store.get(memory_id)
            if result is None:
                return jsonify({"error": "Memory not found"}), 404
            entry, content = result
            return jsonify({"entry": _entry_to_dict(entry), "content": _content_to_dict(content)})
        except Exception as e:
            log.error(f"Error getting memory: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories", methods=["POST"])
    def create_memory():
        try:
            store = _get_memory_store()
            data = request.get_json() or {}
            entry = store.create(
                name=data.get("name", "Untitled"),
                summary=data.get("summary", ""),
                body=data.get("body", ""),
                memory_type=MemoryType(data.get("memory_type", "fact")),
                tags=data.get("tags", []),
                confidence=float(data.get("confidence", 0.5)),
                priority=int(data.get("priority", 50)),
                source=data.get("source", "manual"),
                ttl_days=data.get("ttl_days"),
                metadata=data.get("metadata", {}),
            )
            return jsonify({"entry": _entry_to_dict(entry)}), 201
        except Exception as e:
            log.error(f"Error creating memory: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories/<memory_id>", methods=["PUT"])
    def update_memory(memory_id):
        try:
            store = _get_memory_store()
            data = request.get_json() or {}
            memory_type = MemoryType(data.get("memory_type")) if data.get("memory_type") else None
            status = RecordStatus(data.get("status")) if data.get("status") else None
            success = store.update(
                memory_id,
                name=data.get("name"),
                summary=data.get("summary"),
                body=data.get("body"),
                memory_type=memory_type,
                tags=data.get("tags"),
                confidence=data.get("confidence"),
                priority=data.get("priority"),
                status=status,
                ttl_days=data.get("ttl_days"),
                metadata=data.get("metadata"),
            )
            if not success:
                return jsonify({"error": "Memory not found"}), 404
            entry, content = store.get(memory_id)
            return jsonify({"entry": _entry_to_dict(entry), "content": _content_to_dict(content)})
        except Exception as e:
            log.error(f"Error updating memory: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories/<memory_id>", methods=["DELETE"])
    def delete_memory(memory_id):
        try:
            store = _get_memory_store()
            if store.delete(memory_id):
                return jsonify({"status": "deleted"})
            return jsonify({"error": "Memory not found"}), 404
        except Exception as e:
            log.error(f"Error deleting memory: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories/query", methods=["POST"])
    def query_memories():
        try:
            store = _get_memory_store()
            data = request.get_json() or {}
            from nexus.memory.types import MemoryQuery

            query = MemoryQuery(
                text=data.get("text", ""),
                limit=int(data.get("limit", 8)),
                budget_tokens=int(data.get("budget_tokens", 2000)),
                relation_hops=int(data.get("relation_hops", 1)),
                required_tags=set(data.get("required_tags", [])),
                context_layers=set(data.get("context_layers", ["l0", "l1", "l2"])),
                memory_types=set(data.get("memory_types", [])),
            )
            result = store.recall(query)
            return jsonify(
                {
                    "entries": [_entry_to_dict(e) for e in result.entries],
                    "contents": {k: _content_to_dict(c) for k, c in result.contents.items()},
                    "candidates_scanned": result.candidates_scanned,
                    "used_tokens": result.used_tokens,
                    "score_breakdown": [
                        {
                            "memory_id": sb.memory_id,
                            "lexical_score": sb.lexical_score,
                            "recency_score": sb.recency_score,
                            "priority_score": sb.priority_score,
                            "graph_score": sb.graph_score,
                            "final_score": sb.final_score,
                            "selected": sb.selected,
                        }
                        for sb in result.score_breakdown
                    ],
                    "dropped_candidates": [
                        {
                            "memory_id": d.memory_id,
                            "reason": d.reason,
                            "final_score": d.final_score,
                            "token_cost": d.token_cost,
                        }
                        for d in result.dropped_candidates
                    ],
                }
            )
        except Exception as e:
            log.error(f"Error querying memories: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories/<memory_id>/feedback", methods=["POST"])
    def memory_feedback(memory_id):
        try:
            store = _get_memory_store()
            data = request.get_json() or {}
            action = data.get("action", "confirm")
            reason = data.get("reason", "")
            entry = store.get(memory_id)
            if entry is None:
                return jsonify({"error": "Memory not found"}), 404
            if action == "delete":
                store.delete(memory_id)
                return jsonify({"status": "deleted"})
            elif action == "reject":
                store.update(
                    memory_id, metadata={"feedback_rejected": True, "feedback_reason": reason}
                )
            elif action == "confirm":
                store.update(
                    memory_id, metadata={"feedback_confirmed": True, "feedback_reason": reason}
                )
            entry, _ = store.get(memory_id)
            return jsonify({"entry": _entry_to_dict(entry)})
        except Exception as e:
            log.error(f"Error providing memory feedback: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories/consolidate", methods=["POST"])
    def consolidate_memories():
        try:
            from nexus.memory.lifecycle import consolidate_entries, ConsolidationPolicy

            store = _get_memory_store()
            data = request.get_json() or {}
            policy = ConsolidationPolicy(
                decay_per_day=int(data.get("decay_per_day", 1)),
                min_priority=int(data.get("min_priority", 5)),
                dedupe_enabled=bool(data.get("dedupe_enabled", True)),
                archive_expired=bool(data.get("archive_expired", True)),
            )
            entries = list(store._index.list())
            touched = consolidate_entries(entries, policy=policy)
            for entry in touched:
                store._index.upsert(entry)
            return jsonify(
                {
                    "status": "consolidated",
                    "touched_count": len(touched),
                    "entries": [_entry_to_dict(e) for e in touched],
                }
            )
        except Exception as e:
            log.error(f"Error consolidating memories: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories/suggest-archives", methods=["GET"])
    def suggest_memory_archives():
        try:
            from nexus.memory.lifecycle import suggest_archives

            store = _get_memory_store()
            max_age_days = int(request.args.get("max_age_days", 90))
            max_entries = int(request.args.get("max_entries", 100))
            entries = list(store._index.list())
            suggested = suggest_archives(
                entries, max_age_days=max_age_days, max_entries=max_entries
            )
            return jsonify({"suggested_ids": suggested, "count": len(suggested)})
        except Exception as e:
            log.error(f"Error suggesting archives: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/memories/stats", methods=["GET"])
    def memory_stats():
        try:
            store = _get_memory_store()
            entries = list(store._index.list())
            stats = {
                "total": len(entries),
                "by_status": {"active": 0, "superseded": 0, "archived": 0},
                "by_type": {"fact": 0, "episode": 0, "preference": 0, "procedure": 0},
                "avg_confidence": 0.0,
                "avg_priority": 0.0,
            }
            total_confidence = 0.0
            total_priority = 0.0
            for entry in entries:
                stats["by_status"][entry.status.value] = (
                    stats["by_status"].get(entry.status.value, 0) + 1
                )
                stats["by_type"][entry.memory_type.value] = (
                    stats["by_type"].get(entry.memory_type.value, 0) + 1
                )
                total_confidence += entry.confidence
                total_priority += entry.priority
            if entries:
                stats["avg_confidence"] = total_confidence / len(entries)
                stats["avg_priority"] = total_priority / len(entries)
            return jsonify(stats)
        except Exception as e:
            log.error(f"Error getting memory stats: {e}")
            return jsonify({"error": str(e)}), 500
